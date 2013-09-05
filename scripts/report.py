#!/usr/bin/env python
# Based on iTunesConnectArchiver by Rogue Amoeba Software, LLC

import sys, os, time
import optparse
import sqlite3
import re
import json

class AppStoreSalesDataStorage(object):
    def __init__(self, dbPath):
        dbPath = os.path.abspath(dbPath)
        if not os.path.isfile(dbPath):
            raise Exception("Database file does not exist at %s" % dbPath)

        self._db = sqlite3.connect(dbPath)
    
    def fetchOverallStats(self, pids):
        dayRanges=[1,2,3,4,5,6,7,30,90,180,365,9999]

        args = map(lambda x: str(x), pids)
        args.insert(0, "placeholder")

        statsSql = '''SELECT (julianday('now') - julianday(min(sales.date))), SUM(sales.incomeUnits), SUM(sales.incomeRevenue)
                      FROM sales
                      WHERE ((julianday(sales.date) BETWEEN (julianday(date('now'))-?) AND (julianday(date('now')))) AND sales.incomeRevenue > 0 AND sales.pid IN ({pf}))
                      ORDER by sales.date DESC'''
        statsSql = statsSql.format(pf = ', '.join(['?']*len(pids)))
        
        perDaySql = '''SELECT SUM(sales.incomeRevenue), SUM(sales.incomeUnits) FROM sales
                       WHERE (date(sales.date) == date('now', ?) AND sales.incomeRevenue > 0 AND sales.pid IN ({pf}))
                       ORDER by sales.date DESC'''
        perDaySql = perDaySql.format(pf = ', '.join(['?']*len(pids)))

        #args[0] = 100
        #cursor = self._db.execute(statsSql, args)
        #print cursor.fetchall()
        #sys.exit(0) #return {}
        ###########
        
        stats = {}
        for daysAgo in dayRanges:
            args[0] = daysAgo
            cursor = self._db.execute(statsSql, args)
            (actualDaysAgo, sumUnits, sumRevenue) = cursor.fetchone()
            
            if actualDaysAgo != None:
                daysAgo = int(actualDaysAgo)
                
                args[0] = '%d day' % -daysAgo
                perDayCursor = self._db.execute(perDaySql, args)
                (revenue, units) = perDayCursor.fetchone()
            else:
                revenue = 0
                units = 0
            
            stats[daysAgo] = (max(sumUnits, 0), max(sumRevenue, 0), revenue, units)
        
        return stats
    
    def fetchAllProductIDs(self):
        cursor = self._db.execute('SELECT pid FROM sales WHERE 1 GROUP BY pid ')
        return [row[0] for row in cursor.fetchall()]
    
    def fetchStatsForProductID(self, pid, reportRange=()):
        if reportRange:
            cursor = self._db.execute('SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue), sales.unitsByCountry FROM sales WHERE pid=? AND date >= ? AND date <=? GROUP BY sales.date ORDER by sales.date DESC', (pid,reportRange[0],reportRange[1]))
        else:
            cursor = self._db.execute('SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue), sales.unitsByCountry FROM sales WHERE pid=? GROUP BY sales.date ORDER by sales.date DESC', (pid,))
        return cursor.fetchall() # Pretty much exactly what we want anyway


class AppStoreSalesDataReporting(object):
    def __init__(self, dataStorage, reportRange = None):
        self._dataStorage = dataStorage
        if reportRange == None:
            reportRange = ()
        self._reportRange = reportRange

    def _sortedOverallStats(self, stats):
        return [(key, stats[key]) for key in sorted(stats.keys())]
    
    def _overallSales(self, pids):
        overallStats = self._dataStorage.fetchOverallStats(pids)
        
        output = '<h3 class="resultsHeader">Results, overall</h3>'
        output += '<table class="full">\n'
        output += '<tr>\n'
        output += '<td>Days ago</td>'

        # If there is no data in the first days, skip them. This makes the average values
        # more useful when there is no data for a few days due to problems with iTC.
        firstDayOffset = -1
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            if firstDayOffset == -1:
                firstDayOffset = daysAgo
            output += '<td>%d</td>' % (daysAgo)
        output += '\n</tr>\n'

        if firstDayOffset == -1:
            firstDayOffset = 0

        output += '<tr>\n'
        output += '<td>Units</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%d</td>' % stats[3]
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Average Units</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.1f</td>' % (stats[0] / float(max(1, daysAgo - firstDayOffset + 1)))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Acc. Units</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%d</td>' % stats[0]
        output += '\n</tr>\n'

        output += '<tr>\n'
        output += '<td>Revenue</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f kr</td>' % stats[2]
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Average Revenue</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f kr</td>' % (stats[1] / max(1, daysAgo - firstDayOffset + 1))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Acc. Revenue</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f kr</td>' % stats[1]
        output += '\n</tr>\n'

        output += '<tr class="minusTaxes">\n'
        output += '<td>60% of Acc. Rev.</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f kr</td>' % (0.6 * stats[1])
        output += '\n</tr>\n'

        output += '</table>\n\n'
        
        return output

    def _fixupUnitsByCountry(self, str):
        countries = str.split()
        countries.sort()
        p = re.compile('=')
        out = ''
        for country in countries:
            if out != '':
                out += ', '
            out += p.sub(': ', country)
        return out

    def _chartForProductID(self, pid, name):
        output = '<h3 class="resultsHeader">Results: ' + name + '</h3>'
        output += '<table>'
        
        productChart = self._dataStorage.fetchStatsForProductID(pid, self._reportRange)
        
        rows = [row[2] for row in productChart]
        if len(rows):
            topRevenue = max(rows)
        else:
            topRevenue = 0
        
        totalUnits = 0
        totalRevenue = 0
        count = 0
        
        for row in productChart:
            (date, units, revenue, unitsByCountry) = row
            
            totalUnits += units
            totalRevenue += revenue
            
            output += '<tr>\n'
            output += '<td class="date">%s</td>' % date
            output += '<td class="units">%d</td>' % units
            output += '<td class="revenue">%.0f kr</td>' % revenue
            output += '<td class="countries">%s</td>' % self._fixupUnitsByCountry(unitsByCountry)
            output += '\n</tr>\n'

            if topRevenue:
                percentageOfTopRevenue = revenue / topRevenue
            else:
                percentageOfTopRevenue = 0
            numberOfColumns = int(percentageOfTopRevenue * 50)
            
            count += 1
            if count > 6:
                break
        
        output += '<tr class="total">\n'
        output += '<td>Total</td>'
        output += '<td>%d</td>' % totalUnits
        output += '<td>%.0f kr</td>' % totalRevenue
        output += '<td class="countries"></td>'
        output += '\n</tr>\n'
        
        output += '</table>\n\n'
        
        return output
    
    def generateReport(self, pids=[]):
        report = ''
        
        if pids == []:
            pids = self._dataStorage.fetchAllProductIDs()
        else:
            pids = pids.split(' ')
  
        report += self._overallSales(pids)
        report += '<br>\n'

        #print pids
        #print report
        #sys.exit(0)

        try:
            pidMapStream = open(os.path.expanduser('~/.wendy/pidMap.json'), 'r').read()
            pidMapData = json.loads(pidMapStream)
        except:
            pidMapData = None

        for pid in pids: #self._dataStorage.fetchAllProductIDs():
            pidStr = str(pid)
            try:
                name = pidMapData[pidStr]
            except:
                name = pidStr

            #if pids != [] and not pidStr in pids:
            #    continue

            report += self._chartForProductID(pidStr, name)
        report += '<br>\n'
        
        return report

def main(sysArgs):
    usage = '%prog: [options]'
    parser = optparse.OptionParser(usage = usage)
    
    parser.add_option('-d', '--directory',
                      dest='directory', default=None,
                      metavar='/PATH/TO/WORKING-DIR', help='Directory path for database and reports (required)')
    parser.add_option('-p', '--pids',
                      dest='pids', default=[],
                      metavar='LIST OF PIDS', help='List of pids to report)')

    (options, arguments) = parser.parse_args(sysArgs)
    optionsValid = (options.directory != None)
    options.reportRange = ()
    if not optionsValid:
        parser.print_help(file = sys.stderr)
        sys.exit(-1)

    root = os.path.expanduser(options.directory)
    dataStorage = AppStoreSalesDataStorage(os.path.join(root, 'sales.sqlite'))

    reporter = AppStoreSalesDataReporting(dataStorage, options.reportRange)
    print reporter.generateReport(options.pids)

if __name__ == '__main__':
    main(sys.argv[1:])

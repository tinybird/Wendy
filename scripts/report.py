#!/usr/bin/env python
# Based on iTunesConnectArchiver by Rogue Amoeba Software, LLC

import sys, os, time
import optparse
import sqlite3
import re

class AppStoreSalesDataStorage(object):
    def __init__(self, dbPath):
        dbPath = os.path.abspath(dbPath)
        if not os.path.isfile(dbPath):
            raise Exception("Database file does not exist at %s" % dbPath)

        self._db = sqlite3.connect(dbPath)
    
    def fetchOverallStats(self, dayRanges=[-1,-2,1,2,3,4,5,6,7,30,90,180,365,9999]):
        sqlDaysoAgoStats = '''SELECT  (julianday('now') - julianday(min(sales.date))) as daysAgo,
                                    SUM(sales.incomeUnits) as units,
                                    SUM(sales.incomeRevenue) as revenue
                            FROM sales
                            WHERE ((julianday(sales.date) BETWEEN (julianday(date('now'))-?) AND (julianday(date('now')))) AND sales.incomeRevenue>0) ORDER by sales.date DESC'''
        
        stats = {}
        for daysAgo in dayRanges:
            if daysAgo == -1:
                daysAgo = time.localtime()[2] #MonthDay
            elif daysAgo == -2:
                daysAgo = time.localtime()[-2] #YearDay
            
            cursor = self._db.execute(sqlDaysoAgoStats, (daysAgo,))
            (actualDaysAgo, units, revenue) = cursor.fetchone()
            
            if actualDaysAgo != None:
                daysAgo = int(actualDaysAgo-1) #Think this is correct, I always mess this caclulation up
            
            stats[daysAgo] = (max(units,0), max(revenue,0))
        
        return stats
    
    def fetchAllProductIDs(self):
        cursor = self._db.execute('SELECT pid FROM sales WHERE 1 GROUP BY pid ')
        return [row[0] for row in cursor.fetchall()]
    
    def fetchStatsForProductID(self, pid, reportRange=()):
        if reportRange:
            cursor = self._db.execute('SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue), sales.unitsByCountry FROM sales WHERE pid=? AND date >= ? AND date <=? GROUP BY sales.date ORDER by sales.date DESC', (pid,reportRange[0],reportRange[1]))
        else:
            cursor = self._db.execute('SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue), sales.unitsByCountry FROM sales WHERE pid=? GROUP BY sales.date ORDER by sales.date DESC', (pid,))
        return cursor.fetchall() #Pretty much exactly what we want anyway


class AppStoreSalesDataReporting(object):
    def __init__(self, dataStorage, reportRange = None):
        self._dataStorage = dataStorage
        if reportRange == None:
            reportRange = ()
        self._reportRange = reportRange

    def _sortedOverallStats(self, stats):
        return [(key, stats[key]) for key in sorted(stats.keys())]
    
    def _overallSales(self):
        overallStats = self._dataStorage.fetchOverallStats()
        
        output = '<table class="full">\n'
        output += '<tr>\n'
        output += '<td>Days ago</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%d</td>' % (daysAgo)
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Units/day</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.1f</td>' % (stats[0] / float(max(1, daysAgo)))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Units</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%d</td>' % stats[0]
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Rev/day</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f SEK</td>' % (stats[1] / max(1, daysAgo))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Revenue</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f SEK</td>' % stats[1]
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

    def _chartForProductID(self, pid):
        output = '<table>'
        
        productChart = self._dataStorage.fetchStatsForProductID(pid, self._reportRange)
        
        rows = [row[2] for row in productChart]
        if len(rows):
            topRevenue = max(rows)
        else:
            topRevenue = 0
        
        totalUnits = 0
        totalRevenue = 0
        
        for row in productChart:
            (date, units, revenue, unitsByCountry) = row
            
            totalUnits += units
            totalRevenue += revenue
            
            output += '<tr>\n'
            output += '<td>%s</td>' % date
            output += '<td>%d</td>' % units
            output += '<td>%.0f SEK</td>' % revenue
            output += '<td class="countries">%s</td>' % self._fixupUnitsByCountry(unitsByCountry)
            output += '\n</tr>\n'

            if topRevenue:
                percentageOfTopRevenue = revenue / topRevenue
            else:
                percentageOfTopRevenue = 0
            numberOfColumns = int(percentageOfTopRevenue * 50)
        
        output += '<tr>\n'
        output += '<td>Total</td>'
        output += '<td>%d</td>' % totalUnits
        output += '<td>%.0f SEK</td>' % totalRevenue
        output += '<td class="countries"></td>'
        output += '\n</tr>\n'
        
        output += '</table>\n\n'
        
        return output
    
    def generateReport(self):
        report = ''
        
        report += '<b>Overall:</b>\n'
        report += self._overallSales()
        
        report += '<br/>\n'
        for pid in self._dataStorage.fetchAllProductIDs():
            report += '<br/><b>Product: %s</b>\n' % pid
            report += self._chartForProductID(pid)
        report += '<br/>\n'
        
        return report

def main(sysArgs):
    usage = '%prog: [options]'
    parser = optparse.OptionParser(usage = usage)
    
    parser.add_option('-d', '--directory',
                      dest='directory', default=None,
                      metavar='/PATH/TO/WORKING-DIR', help='Directory path for database and reports (required)')
    
    (options, arguments) = parser.parse_args(sysArgs)
    
    optionsValid = (options.directory != None)
    
    options.reportRange = ()
    
    if not optionsValid:
        parser.print_help(file = sys.stderr)
        sys.exit(-1)
    
    root = os.path.expanduser(options.directory)
    dataStorage = AppStoreSalesDataStorage(os.path.join(root, 'sales.sqlite'))
    
    reporter = AppStoreSalesDataReporting(dataStorage, options.reportRange)
    print reporter.generateReport()

if __name__ == '__main__':
    main(sys.argv[1:])

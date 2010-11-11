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
    
    def fetchOverallStats(self, dayRanges=[1,2,3,4,5,6,7,30,90,180,365,9999]):
        statsSql = '''SELECT (julianday('now') - julianday(min(sales.date))), SUM(sales.incomeUnits), SUM(sales.incomeRevenue)
                      FROM sales
                      WHERE ((julianday(sales.date) BETWEEN (julianday(date('now'))-?) AND (julianday(date('now')))) AND sales.incomeRevenue > 0)
                      ORDER by sales.date DESC'''

        perDaySql = '''SELECT SUM(sales.incomeRevenue), SUM(sales.incomeUnits) FROM sales
                       WHERE (date(sales.date) == date('now', ?) AND sales.incomeRevenue > 0)
                       ORDER by sales.date DESC'''
        
        stats = {}
        for daysAgo in dayRanges:
            cursor = self._db.execute(statsSql, (daysAgo,))
            (actualDaysAgo, sumUnits, sumRevenue) = cursor.fetchone()
            
            if actualDaysAgo != None:
                daysAgo = int(actualDaysAgo)
                
                perDayCursor = self._db.execute(perDaySql, ('%d day' % -daysAgo,))
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
    
    def _overallSales(self):
        overallStats = self._dataStorage.fetchOverallStats()
        
        output = '<table class="full">\n'
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
            output += '<td>%.0f SEK</td>' % stats[2]
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Average Revenue</td>'
        for (daysAgo, stats) in self._sortedOverallStats(overallStats):
            output += '<td>%.0f SEK</td>' % (stats[1] / max(1, daysAgo - firstDayOffset + 1))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Acc. Revenue</td>'
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
        count = 0
        
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
            
            count += 1
            if count > 9:
                break
        
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

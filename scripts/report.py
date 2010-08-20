#!/usr/bin/env python
# Based on iTunesConnectArchiver by Rogue Amoeba Software, LLC

import sys, os, time
import optparse
import sqlite3

class AppStoreSalesDataStorage(object):
    def __init__( self, dbPath ):
        self._db = sqlite3.connect(dbPath)
        
        self._db.execute('''CREATE TABLE IF NOT EXISTS sales (
                            id INTEGER PRIMARY KEY,
                            date CHAR(16),
                            pid INTEGER,
                            incomeRevenue REAL,
                            incomeUnits INTEGER,
                            refundLoss REAL,
                            refundUnits INTEGER,
                            unitsByCountry BLOB,
                            revenueByCurrency BLOB
                       ) ''')
        self._db.commit()
    
    def storeDays(self, parsedDays):
        for day in parsedDays: self.storeDay(day)
    
    def storeDay(self, dayStats):
        # Convert from python bits to sqlite bits
        sqlDayStats = dayStats.copy()
        sqlDayStats['unitsByCountry'] = ' '.join( ['%s=%d' % (country,units) for (country, units) in dayStats['unitsByCountry'].iteritems()] )
        sqlDayStats['revenueByCurrency'] = ' '.join( ['%s=%.02f' % (currency,float(amount)) for (currency, amount) in dayStats['revenueByCurrency'].iteritems()] )
        
        sqlDayStats['incomeRevenue'] = float(dayStats.get('incomeRevenue',0))
        sqlDayStats['refundLoss'] = float(dayStats.get('refundLoss', 0))
        
        cursor = self._db.execute( 'SELECT id FROM sales WHERE date=? and pid=?', (sqlDayStats['date'], sqlDayStats['pid']) )
        row = cursor.fetchone()
        if row and len(row):
            id = row[0]
        else:
            id = None
        
        allKeys = ['id',]
        allKeys.extend( sqlDayStats.keys() )
        allValues = [id,]
        allValues.extend( sqlDayStats.values() )
        
        sql = 'INSERT OR REPLACE INTO sales '
        sql += '(' + (', '.join(allKeys)) + ') '
        sql += 'VALUES (' + ('?, '*(len(allValues)-1)) + '?' + ')'
        
        self._db.execute( sql, allValues )
        self._db.commit()
    
    def fetchOverallStats( self, dayRanges=[-1,-2,1,2,3,4,5,6,7,30,90,180,365,9999] ):
        
        sqlDaysoAgoStats = '''SELECT  (julianday('now') - julianday(min(sales.date))) as daysAgo,
                                    SUM( sales.incomeUnits ) as units,
                                    SUM( sales.incomeRevenue) as revenue
                            FROM sales
                            WHERE (julianday(sales.date) BETWEEN (julianday(date('now'))-?) AND (julianday(date('now')))) AND sales.incomeRevenue>0 '''
        
        stats = {}
        for daysAgo in dayRanges:
            if daysAgo == -1:
                daysAgo = time.localtime()[2] #MonthDay
            elif daysAgo == -2:
                daysAgo = time.localtime()[-2] #YearDay
            
            cursor = self._db.execute( sqlDaysoAgoStats, (daysAgo,) )
            (actualDaysAgo, units, revenue) = cursor.fetchone()
            
            if actualDaysAgo != None:
                daysAgo = int(actualDaysAgo-1) #Think this is correct, I always mess this caclulation up
            
            stats[daysAgo] = (max(units,0), max(revenue,0))
        
        return stats
    
    def fetchAllProductIDs( self ):
        cursor = self._db.execute( 'SELECT pid FROM sales WHERE 1 GROUP BY pid ' )
        return [row[0] for row in cursor.fetchall()]
    
    
    def fetchStatsForProductID( self, pid, reportRange=() ):
        
        if reportRange:
            cursor = self._db.execute( 'SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue) FROM sales WHERE pid=? AND date >= ? AND date <=? GROUP BY sales.date ORDER by sales.date DESC', (pid,reportRange[0],reportRange[1]) )
        else:
            cursor = self._db.execute( 'SELECT sales.date, SUM(sales.incomeUnits), SUM(sales.incomeRevenue) FROM sales WHERE pid=? GROUP BY sales.date ORDER by sales.date DESC', (pid,) )
        return cursor.fetchall() #Pretty much exactly what we want anyway


class AppStoreSalesDataReporting(object):
    def __init__(self, dataStorage, reportRange=None):
        self._dataStorage = dataStorage
        if reportRange == None:
            reportRange = ()
        self._reportRange = reportRange
    
    def _overallSales(self):
        overallStats = self._dataStorage.fetchOverallStats()
        
        output = '<table class="full">\n'
        output += '<tr>\n'
        output += '<td>Days ago</td>'
        for (daysAgo, stats) in overallStats.iteritems():
            output += '<td>%d</td>' % (daysAgo)
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Units/day</td>'
        for (daysAgo, stats) in overallStats.iteritems():
            output += '<td>%.1f</td>' % (stats[0] / float(max(1, daysAgo)))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Units</td>'
        for (daysAgo, stats) in overallStats.iteritems():
            output += '<td>%d</td>' % stats[0]
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Rev/day</td>'
        for (daysAgo, stats) in overallStats.iteritems():
            output += '<td>%.0f SEK</td>' % (stats[1] / max(1, daysAgo))
        output += '\n</tr>\n'
        
        output += '<tr>\n'
        output += '<td>Revenue</td>'
        for (daysAgo, stats) in overallStats.iteritems():
            output += '<td>%.0f SEK</td>' % stats[1]
        output += '\n</tr>\n'

        output += '</table>\n\n'
        
        return output

    def _chartForProductID( self, pid ):
        output = '<table>'
        
        productChart = self._dataStorage.fetchStatsForProductID( pid, self._reportRange )
        
        rows = [row[2] for row in productChart]
        if len(rows):
            topRevenue = max(rows)
        else:
            topRevenue = 0
        
        totalUnits = 0
        totalRevenue = 0
        
        for row in productChart:
            (date, units, revenue) = row
            
            totalUnits += units
            totalRevenue += revenue
            
            output += '<tr>\n'
            output += '<td>%s</td>' % date
            output += '<td>%d</td>' % units
            output += '<td>%.0f SEK</td>' % revenue
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
        output += '\n</tr>\n'
        
        output += '</table>\n\n'
        
        return output
    
    def generateReport( self ):
        report = ''
        
        report += '<b>Overall:</b>\n'
        report += self._overallSales()
        
        report += '<br/>\n'
        for pid in self._dataStorage.fetchAllProductIDs():
            report += '<br/><b>Product: %s</b>\n' % pid
            report += self._chartForProductID( pid )
        report += '<br/>\n'
        
        return report

def main(sysArgs):
    #Parse the cmd-line args
    usage = '%prog: [options]'
    parser = optparse.OptionParser(usage = usage)
    
    parser.add_option('-d', '--database',
                        dest = 'databasePath', default = None,
                        metavar = '/PATH/TO/DB', help = 'Database storage file path (required)')
    
    (options, arguments) = parser.parse_args(sysArgs)
    
    optionsValid = (options.databasePath != None)
    
    options.reportRange = ()
    
    if not optionsValid:
        parser.print_help(file = sys.stderr)
        sys.exit(-1)
    
    dataStorage = AppStoreSalesDataStorage(os.path.expanduser(options.databasePath))
    
    reporter = AppStoreSalesDataReporting(dataStorage, options.reportRange)
    print reporter.generateReport()

if __name__ == '__main__':
    main(sys.argv[1:])

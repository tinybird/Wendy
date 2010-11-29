#!/usr/bin/env python
# Based on iTunesConnectArchiver v1.0.0 by Rogue Amoeba Software, LLC
# See the readme for license and details about the original source.

import sys, os, time
import gzip, StringIO
import csv, decimal
import sqlite3
import optparse
import urllib, urllib2
import xml.dom.minidom  #Used for currency converter
import shutil

class AppStoreSalesDataFetcher(object):
  def __init__(self, directory):
    self.reportPath = os.path.join(directory, 'OriginalReports')
    self.donePath = os.path.join(directory, 'DoneReports')
  
  def fetchAll(self):
    print "Getting reports at %s" % self.reportPath
    
    dailyData = []
    for filename in os.listdir(self.reportPath):
      if not filename.endswith('.txt.gz'):
        continue
      
      path = os.path.join(self.reportPath, filename)
      #print path

      f = gzip.open(path, 'rb')
      dailyData.append(f.read())
      f.close()    

    return dailyData

  def cleanUp(self):
    print "Cleaning out reports at %s" % self.reportPath
    
    try:
      os.makedirs(self.donePath)
    except:
      pass

    for filename in os.listdir(self.reportPath):
      if not filename.endswith('.txt.gz'):
        continue

      fromPath = os.path.join(self.reportPath, filename)
      toPath = os.path.join(self.donePath, filename)
      shutil.move(fromPath, toPath)

class XavierMediaCurrencyConverter(object):
  __cachedTables = {} #We shared this between classes to save from hitting the webserver so hard
  
  def conversionTableForDate(self, date):
    dateStr = time.strftime('%Y/%m/%d', date)
                
    table = self.__cachedTables.get(dateStr, None)
    if table == None:
      table = []
                        
      #We do little error checking here, because I'm not really in the mood to be paranoid
      #Should just wrap it in giant try: block at some point
                        
      socket = urllib2.urlopen('http://api.finance.xaviermedia.com/api/latest.xml')
      xmlData = socket.read()
      socket.close()
                        
      xmlTree = xml.dom.minidom.parseString(xmlData)
      baseCurrency = xmlTree.getElementsByTagName('basecurrency')[0].firstChild.data
      fxElements = xmlTree.getElementsByTagName('fx')
      for element in fxElements:
        targetCurrency = element.getElementsByTagName('currency_code')[0].firstChild.data
        rate = decimal.Decimal(element.getElementsByTagName('rate')[0].firstChild.data)
                                
        entry = {'base': baseCurrency, 'target': targetCurrency, 'rate': rate }
        table.append(entry)
                        
      self.__cachedTables[dateStr] = table
                
    return table
        
  def convert(self, startCurrency, targetCurrency, dateTuple, startAmount):
    if startCurrency == targetCurrency:
      return startAmount
    if startAmount == 0:
      return startAmount

    # No MXN support in xavier :/
    if startCurrency == 'MXN' and targetCurrency == 'SEK':
        return startAmount * decimal.Decimal('0.560267654')
    
    conversionTable = self.conversionTableForDate(dateTuple)
    
    startEntry = [e for e in conversionTable if e['target'] == startCurrency][0]
    amountInStartBase = startAmount / startEntry['rate']
                
    endEntry = [e for e in conversionTable if e['target'] == targetCurrency][0]
    if endEntry['base'] != startEntry['base']: #Lots of code could handle this case
      return None
                
    amountInEndBase = endEntry['rate'] * amountInStartBase
                
    return amountInEndBase

class AppStoreSalesDataMunger(object):
  def _combineDayData(self, rowSet):
    combinedData = {}
                
    nonRefundRows = [row for row in rowSet if row['units'] >= 0]
    refundRows = [row for row in rowSet if row['units'] < 0]
                
    totalRevenue = 0
    for row in nonRefundRows:
      totalRevenue += (row['priceInSellerCurrency'] * row['units'])
    combinedData['incomeRevenue'] = totalRevenue
                
    totalUnits = sum([row['units'] for row in rowSet])
    combinedData['incomeUnits'] = totalUnits
                
    unitsByCountry = {}
    for row in nonRefundRows:
      countryCode = row['country']
      countryTotal = unitsByCountry.get(countryCode, 0)
      countryTotal += row['units']
      unitsByCountry[countryCode] = countryTotal
    combinedData['unitsByCountry'] = unitsByCountry
                
    revenueByCurrency = {}
    for row in nonRefundRows:
      currencyType = row['buyerCurrencyType']
      currencyTotal = revenueByCurrency.get(currencyType, 0)
      currencyTotal += (row['priceInBuyerCurrency'] * row['units'])
      revenueByCurrency[currencyType] = currencyTotal
    combinedData['revenueByCurrency'] = revenueByCurrency
                
    if len(refundRows):
      totalRefundsLoss = 0
      for row in refundRows:
        totalRefundsLoss += (row['priceInSellerCurrency'] * row['units'])
      combinedData['refundLoss'] = totalRefundsLoss
                        
      totalRefundsUnits = 0
      for row in refundRows:
        totalRefundsUnits += row['units']
      combinedData['refundUnits'] = totalRefundsUnits
                
    return combinedData
        
  def munge(self, daysData, currency):
    allRows = []
    currencyConverter = XavierMediaCurrencyConverter()
    for day in daysData:
      reader = csv.reader(StringIO.StringIO(day), 'excel-tab')
      for row in reader:
        if not len(row):
          continue
        if row[0] != 'APPLE':
          continue

        rowFields = {}
        rowFields['productID']= row[2] # Vendor id/SKU
        rowFields['date'] = time.strptime(row[9].strip(), '%m/%d/%Y') # Begin date, was 11
        rowFields['salesType'] = int(row[6]) # Product type identifier, was 8
        rowFields['units'] = int(row[7]) # Units, was 9
        rowFields['buyerCurrencyType'] = row[11] # Customer currency, was 13
        rowFields['priceInBuyerCurrency'] = decimal.Decimal(row[15]) # Customer price, was 19
        rowFields['sellerCurrencyType'] = currency
        rowFields['priceInSellerCurrency'] = rowFields['priceInBuyerCurrency']
        rowFields['priceInSellerCurrency'] = currencyConverter.convert(rowFields['buyerCurrencyType'],
            rowFields['sellerCurrencyType'], rowFields['date'], rowFields['priceInBuyerCurrency'])
        rowFields['country'] = row[12] # Country code, was 14
        
        if rowFields['salesType'] != 7: #We're ignoring Upgrade stats for now
          allRows.append(rowFields)
                
    ### Group our rows by date, and then product, and then process them
    allDates = set([row['date'] for row in allRows])
    allProducts = set([row['productID'] for row in allRows])
                
    outputRows = []
    for date in allDates:
      for product in allProducts:
        subRows = [row for row in allRows if row['date'] == date and row['productID'] == product]
        newRow = self._combineDayData(subRows)
        newRow['date'] = time.strftime('%Y-%m-%d', date)
        newRow['pid'] = product
        outputRows.append(newRow)
                
    outputRows.sort(lambda x,y: cmp(x['date'], y['date']))
                
    return outputRows

class AppStoreSalesDataStorage(object):
  def __init__(self, dbPath):
    self._db = sqlite3.connect(dbPath)
    self._db.execute('''CREATE TABLE IF NOT EXISTS sales(
                                                        id INTEGER PRIMARY KEY,
                                                        date CHAR(16),
                                                        pid TEXT,
                                                        incomeRevenue REAL,
                                                        incomeUnits INTEGER,
                                                        refundLoss REAL,
                                                        refundUnits INTEGER,
                                                        unitsByCountry BLOB,
                                                        revenueByCurrency BLOB
                                          )''')
    self._db.commit()
    
  def storeDays(self, parsedDays):
    for day in parsedDays:
      self.storeDay(day)
    
  def storeDay(self, dayStats):
    # Convert from python bits to sqlite bits
    sqlDayStats = dayStats.copy()
    sqlDayStats['unitsByCountry'] = ' '.join(['%s=%d' % (country,units) for (country, units) in dayStats['unitsByCountry'].iteritems()])
    sqlDayStats['revenueByCurrency'] = ' '.join(['%s=%.02f' % (currency,float(amount)) for (currency, amount) in dayStats['revenueByCurrency'].iteritems()])
      
    sqlDayStats['incomeRevenue'] = float(dayStats.get('incomeRevenue',0))
    sqlDayStats['refundLoss'] = float(dayStats.get('refundLoss', 0))
                
    cursor = self._db.execute('SELECT id FROM sales WHERE date=? and pid=?', (sqlDayStats['date'], sqlDayStats['pid']))
    row = cursor.fetchone()
    if row and len(row):
      id = row[0]
    else:
      id = None
            
    allKeys = ['id',]
    allKeys.extend(sqlDayStats.keys())
    allValues = [id,]
    allValues.extend(sqlDayStats.values())
    
    sql = 'INSERT OR REPLACE INTO sales '
    sql += '(' + (', '.join(allKeys)) + ') '
    sql += 'VALUES (' + ('?, '*(len(allValues)-1)) + '?' + ')'
    
    self._db.execute(sql, allValues)
    self._db.commit()

def main(sysArgs):
  usage = '%prog: [options]'
  parser = optparse.OptionParser(usage=usage)
        
  parser.add_option('-d', '--directory',
                    dest='directory', default=None,
                    metavar='/PATH/TO/WORKING-DIR', help='Directory path for database and reports (required)')
        
  (options, arguments) = parser.parse_args(sysArgs)
  optionsValid = (options.directory != None)
        
  if not optionsValid:
    parser.print_help(file=sys.stderr)
    sys.exit(-1)
  
  root = os.path.expanduser(options.directory)
  dataStorage = AppStoreSalesDataStorage(os.path.join(root, 'sales.sqlite'))
  
  rawSalesData = AppStoreSalesDataFetcher(root).fetchAll()
  parsedSalesData = AppStoreSalesDataMunger().munge(rawSalesData, 'SEK')
  dataStorage.storeDays(parsedSalesData)
  AppStoreSalesDataFetcher(root).cleanUp()

if __name__ == '__main__':
  main(sys.argv[1:])

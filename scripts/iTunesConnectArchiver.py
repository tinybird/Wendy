#!/usr/bin/env python
# iTunesConnectArchiver v1.0.0
# ========================
# Rogue Amoeba Software, LLC
# qdc@rogueamoeba.com
#
# See ReadMe.txt for details & license

import sys, os, time
import urllib, urllib2, cookielib
import gzip, StringIO
import csv, decimal
import xml.dom.minidom	#Used for currency converter
import sqlite3			#Used for persistance
import optparse

import BeautifulSoup

class iTunesConnectCookieJar(cookielib.CookieJar):
	# Copyright 2008 Kirby Turner - thecave.com
	def _cookie_from_cookie_tuple(self, tup, request):
		# More information at: http://bugs.python.org/issue3924
		name, value, standard, rest = tup
		version = standard.get('version', None)
		if version is not None:
			version = version.replace('"', '')
			standard["version"] = version
		return cookielib.CookieJar._cookie_from_cookie_tuple(self, tup, request)

class AppStoreSalesDataFetcher(object):
	
	def __init__( self, appleID, password ):
		self._appleID = appleID
		self._password = password
		
		if not len(self._appleID) or not len(self._password):
			raise RuntimeError( 'Missing or invalid login id/password' )

	def fetchAll( self ):
		# Portions Copyright 2008 Kirby Turner - thecave.com
		
		urlBase = 'https://itts.apple.com%s'
	
		cj = iTunesConnectCookieJar();
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
	
		urlWebsite = urlBase % '/cgi-bin/WebObjects/Piano.woa'
		urlHandle = opener.open(urlWebsite)
		html = urlHandle.read()

		soup = BeautifulSoup.BeautifulSoup( html )
		form = soup.find( 'form', attrs={'name': 'appleConnectForm' } )
		if not form:
			form = soup.find( 'form' ) #Grab anything
		urlActionLogin = urlBase % form['action']
	
		args = {'theAccountName':self._appleID, 'theAccountPW':self._password}
		args['1.Continue.x'] = '0' #This is so stupid
		args['1.Continue.y'] = '0' #As is this
		args['theAuxValue'] = '' #Extra stupid bonus

		args['wosid'] = soup.find( 'input', attrs={'name':'wosid'} )['value']
		
		webFormLoginData = urllib.urlencode(args)
		urlHandle = opener.open(urlActionLogin, webFormLoginData)
		html = urlHandle.read()
		soup = BeautifulSoup.BeautifulSoup( html )
		form = soup.find( 'form', attrs={'name': 'frmVendorPage' } )
		if not form:
			form = soup.find( 'form' ) #Grab anything
		urlDownload = urlBase % form['action']
		
		fieldNameReportType = soup.find( 'select', attrs={'id': 'selReportType'} )['name']
		fieldNameReportPeriod = soup.find( 'select', attrs={'id': 'selDateType'} )['name']
		fieldNameDayOrWeekSelection = soup.find( 'input', attrs={'name': 'hiddenDayOrWeekSelection'} )['name'] #This is kinda redundant
		fieldNameSubmitTypeName = soup.find( 'input', attrs={'name': 'hiddenSubmitTypeName'} )['name'] #This is kinda redundant, too
	
		post = {fieldNameReportType:'Summary', fieldNameReportPeriod:'Daily', fieldNameDayOrWeekSelection:'Daily', fieldNameSubmitTypeName:'ShowDropDown'}
		webFormSalesReportData = urllib.urlencode(post)
		urlHandle = opener.open(urlDownload, webFormSalesReportData)
		html = urlHandle.read()
	
		reportDates = []
	
		soup = BeautifulSoup.BeautifulSoup( html )
		form = soup.find( 'form', attrs={'name': 'frmVendorPage' } )
		if not form:
			form = soup.find( 'form' ) #Grab anything

		urlDownload = urlBase % form['action']
		select = soup.find( 'select', attrs={'id': 'dayorweekdropdown'} )
		fieldNameDayOrWeekDropdown = select['name']
		
		for option in select.findAll('option'):
			reportDates.append( option.string )
	
		dailyData = []
		for downloadReportDate in reportDates:
			post = {fieldNameReportType:'Summary', fieldNameReportPeriod:'Daily', fieldNameDayOrWeekDropdown:downloadReportDate, fieldNameDayOrWeekSelection:'Daily', fieldNameSubmitTypeName:'Download'}
			webFormSalesReportData = urllib.urlencode(post)
			urlHandle = opener.open(urlDownload, webFormSalesReportData)
			try:
				filename = urlHandle.info().getheader('content-disposition').split('=')[1]
			except AttributeError:
				raise
				
			filebuffer = urlHandle.read()
			urlHandle.close()
	
			#Use GzipFile to de-gzip the data
			ioBuffer = StringIO.StringIO( filebuffer )
			gzipIO = gzip.GzipFile( 'rb', fileobj=ioBuffer )
			filebuffer = gzipIO.read()
			
			dailyData.append( filebuffer )
	
		return dailyData

class XavierMediaCurrencyConverter(object):
	
	__cachedTables = {} #We shared this between classes to save from hitting the webserver so hard
	
	def conversionTableForDate( self, date ):
		dateStr = time.strftime( '%Y/%m/%d', date )
		
		table = self.__cachedTables.get( dateStr, None )
		if table == None:
			table = []
			
			#We do little error checking here, because I'm not really in the mood to be paranoid
			#Should just wrap it in giant try: block at some point

			socket = urllib2.urlopen( 'http://api.finance.xaviermedia.com/api/latest.xml' )
			xmlData = socket.read()
			socket.close()

			xmlTree = xml.dom.minidom.parseString( xmlData )
			baseCurrency = xmlTree.getElementsByTagName('basecurrency')[0].firstChild.data
			fxElements = xmlTree.getElementsByTagName( 'fx' )
			for element in fxElements:
				targetCurrency = element.getElementsByTagName( 'currency_code' )[0].firstChild.data
				rate = decimal.Decimal( element.getElementsByTagName( 'rate' )[0].firstChild.data )
				
				entry = {'base': baseCurrency, 'target': targetCurrency, 'rate': rate }
				table.append( entry )
			
			self.__cachedTables[dateStr] = table
		
		return table
				
	def convert( self, startCurrency, targetCurrency, dateTuple, startAmount ):
		if startCurrency == targetCurrency:
			return startAmount
		if startAmount == 0:
			return startAmount
		
		conversionTable = self.conversionTableForDate( dateTuple )
		
		startEntry = [e for e in conversionTable if e['target'] == startCurrency][0]
		amountInStartBase = startAmount / startEntry['rate']

		endEntry = [e for e in conversionTable if e['target'] == targetCurrency][0]
		if endEntry['base'] != startEntry['base']: #Lots of code could handle this case
			return None

		amountInEndBase = endEntry['rate'] * amountInStartBase

		return amountInEndBase

class AppStoreSalesDataMunger(object):

	def _combineDayData( self, rowSet ):
	
		combinedData = {}
	
		nonRefundRows = [row for row in rowSet if row['units'] >= 0]
		refundRows = [row for row in rowSet if row['units'] < 0]
	
		totalRevenue = 0
		for row in nonRefundRows:
			totalRevenue += (row['priceInSellerCurrency'] * row['units'])
		combinedData['incomeRevenue'] = totalRevenue
	
		totalUnits = sum( [row['units'] for row in rowSet] )
		combinedData['incomeUnits'] = totalUnits
		
		unitsByCountry = {}
		for row in nonRefundRows:
			countryCode = row['country']
			countryTotal = unitsByCountry.get( countryCode, 0 )
			countryTotal += row['units']
			unitsByCountry[countryCode] = countryTotal
		combinedData['unitsByCountry'] = unitsByCountry
		
		revenueByCurrency = {}
		for row in nonRefundRows:
			currencyType = row['buyerCurrencyType']
			currencyTotal = revenueByCurrency.get( currencyType, 0 )
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

	def munge( self, daysData, currency ):
	
		### First pass, toss everything we don't need and dictionarize
		allRows = []
		currencyConverter = XavierMediaCurrencyConverter()
		for day in daysData:
			reader = csv.reader( StringIO.StringIO(day), 'excel-tab' ) #This is probably overkill, but what the hell
			for row in reader:
				if not len(row):
					continue
				if row[0] != 'APPLE':
					continue
	
				rowFields = {}
				rowFields['productID']		= row[2]
				rowFields['date']			= time.strptime( row[11], '%m/%d/%Y' )
				rowFields['salesType']		= int(row[8])
				rowFields['units']			= int(row[9])
	
				rowFields['buyerCurrencyType']		= row[15]
				rowFields['priceInBuyerCurrency']	= decimal.Decimal(row[10])
				rowFields['sellerCurrencyType']		= currency
				
				rowFields['priceInSellerCurrency'] = rowFields['priceInBuyerCurrency']
				rowFields['priceInSellerCurrency'] 	= \
					currencyConverter.convert( rowFields['buyerCurrencyType'], rowFields['sellerCurrencyType'], rowFields['date'], rowFields['priceInBuyerCurrency'] )
	
				rowFields['country']		= row[14]
				
				if rowFields['salesType'] != 7: #We're ignoring Upgrade stats for now
					allRows.append( rowFields )
		
		### Group our rows by date, and then product, and then process them
		allDates = set( [row['date'] for row in allRows] )
		allProducts = set( [row['productID'] for row in allRows] )
		
		outputRows = []
		for date in allDates:
			for product in allProducts:
				subRows = [row for row in allRows if row['date'] == date and row['productID'] == product]
				newRow = self._combineDayData( subRows )
				newRow['date'] = time.strftime('%Y-%m-%d', date )
				newRow['pid'] = product
				outputRows.append( newRow )
		
		outputRows.sort( lambda x,y: cmp(x['date'], y['date']) )
	
		return outputRows	


class AppStoreSalesDataStorage(object):
	
	def __init__( self, dbPath ):
		self._db = sqlite3.connect( dbPath )

		self._db.execute( '''CREATE TABLE IF NOT EXISTS sales (
							id INTEGER PRIMARY KEY,
							date CHAR(16),
							pid	INTEGER,
							incomeRevenue REAL,
							incomeUnits INTEGER,
							refundLoss REAL,
							refundUnits INTEGER,
							unitsByCountry BLOB,
							revenueByCurrency BLOB
					   ) ''')
		self._db.commit()

	def storeDays( self, parsedDays ):
		for day in parsedDays: self.storeDay( day )
	
	def storeDay( self, dayStats ):
		
		#Convert from python bits to sqlite bits
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
	
	def __init__( self, dataStorage, reportRange=None ):
		self._dataStorage = dataStorage
		if reportRange == None:
			reportRange = ()
		self._reportRange = reportRange
	
	def _overallSales( self ):
		
		reportLines = ['', '', '', '', '', '', '', '']

		idx = 0
		reportLines[0] += '+--------+'
		reportLines[1] += '|Days Ago|'
		reportLines[2] += '+--------+'
		reportLines[3] += '|Unts/day|'
		reportLines[4] += '|Units   |'
		reportLines[5] += '|Revn/day|'
		reportLines[6] += '|Revenue |'
		reportLines[7] += '+--------+'
		
		overallStats = self._dataStorage.fetchOverallStats()
		for (daysAgo, stats) in overallStats.iteritems():
			reportLines[0] += '--------+'
			reportLines[1] += '{0:^8}|'.format( daysAgo )
			reportLines[2] += '--------+'
			reportLines[3] += '{0:^8}|'.format( '%.1f' % (stats[0]/float(max(1,daysAgo))) )
			reportLines[4] += '{0:^8}|'.format( '%d' % stats[0] )
			reportLines[5] += '{0:^8}|'.format( '$%.0f' % (stats[1]/max(1,daysAgo)) )
			reportLines[6] += '{0:^8}|'.format( '$%.0f' % stats[1] )
			reportLines[7] += '--------+'

		return '\n'.join( reportLines ) + '\n'

	
	def _chartForProductID( self, pid ):
		chart = '\n'
		chart += '+' + ('-'*78) + '+\n'
		
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
			
			chart += '|{0:^12}|{1:>5}|{2:>7}|'.format( date, units, ('$%.0f' % revenue) )
			
			chart += ' '
			if topRevenue:
				percentageOfTopRevenue = (revenue/topRevenue)
			else:
				percentageOfTopRevenue = 0
			numberOfColumns = int(percentageOfTopRevenue*50)
			chart += '#' * numberOfColumns
			chart += ' ' * (50-numberOfColumns)
			chart += '|'
			
			chart += '\n'


		chart += '+' + ('-'*78) + '+\n'

		chart += '|{0:^12}|{1:>5}|{2:>7}|'.format( 'Total', totalUnits, ('$%.0f' % totalRevenue) )
		chart += ' ' * (51)
		chart += '|\n'

		chart += '+' + ('-'*78) + '+\n'
		
		return chart
		
	def generateReport( self ):
		report = ''
		
		if not len(self._reportRange): #Dont support overall in ranged mode
			report += '### Overall:\n'
			report += self._overallSales()
		
		report += '\n'
		for pid in self._dataStorage.fetchAllProductIDs():
			report += '### Product #%s' % pid
			report += self._chartForProductID( pid )
		
		return report

def main(sysArgs):

	#Parse the cmd-line args
	usage = '%prog: [options] [update] [report]'
	parser = optparse.OptionParser( usage=usage )

	parser.add_option( '-d', '--database',
						dest='databasePath', default=None,
						metavar='/PATH/TO/DB', help='Database storage file path (required)' )

	parser.add_option( '-u', '--username',
						dest='username', default=None,
						metavar='USERNAME', help='AppleID account login (required for update)' )

	parser.add_option( '-p', '--password',
						dest='password', default=None,
						metavar='PASS', help='AppleID account password (required for update)' )

	parser.add_option( '-r', '--reportRange',
						dest='reportRange', default=None,
						metavar='RANGE', help='Date range for a report. Format: YYYY-MM-DD:YYYY-MM-DD (optional for report)' )

	(options, arguments) = parser.parse_args(sysArgs)
	
	optionsValid = (options.databasePath != None)
	optionsValid = optionsValid or (('update' in arguments) and (options.username != None and options.password != None))

	if options.reportRange:
		try:
			parts = options.reportRange.split(':')
			time.strptime(parts[0], '%Y-%m-%d' )
			time.strptime(parts[1], '%Y-%m-%d' )
			options.reportRange = tuple(options.reportRange.split(':'))
		except IndexError, ValueError:
			optionsValue = False
	else:
		options.reportRange = ()

	if not optionsValid:
		parser.print_help( file=sys.stderr )
		sys.exit(-1)

	#Actually get some work done
	
	dataStorage = AppStoreSalesDataStorage( os.path.expanduser(options.databasePath) )

	hadValidCommands = False
	if 'update' in arguments:
		rawSalesData = AppStoreSalesDataFetcher( options.username, options.password ).fetchAll()
		parsedSalesData = AppStoreSalesDataMunger().munge( rawSalesData, 'SEK' ) #Should make this an option...
		dataStorage.storeDays( parsedSalesData )
		hadValidCommands = True
	
	if 'report' in arguments:	
		reporter = AppStoreSalesDataReporting( dataStorage, options.reportRange )
		print reporter.generateReport()
		hadValidCommands = True

	if not hadValidCommands:
		parser.print_help( file=sys.stderr )
		sys.exit(-1)

if __name__ == '__main__':
	main(sys.argv[1:])
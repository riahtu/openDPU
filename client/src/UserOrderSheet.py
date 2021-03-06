#!/usr/bin/env python
# -*- coding: utf-8 -*-

from common_utility import getHourlyDatetime, getDailyDatetime, getPeriodTS
from optparse import OptionParser
from datetime import datetime
import pymysql.cursors
import MySQLdb.cursors
import MySQLdb
import traceback
import copy
import sys
import os

class UserOptionParser:
	def __init__(self):
		self._options()

	def _options(self):
		usage = """usage: %prog [options] arg1,arg2 [options] arg1
$ python NilmCluster.py -v -p 2015-01-01_00:00:00 2015-01-02_23:59:59 -s 1 -D edm3_090"""

		parser = OptionParser(usage = usage)
		parser.add_option("-s", "--sids",
			action="store",
			type="str",
			dest="sids",
			nargs=1,
			default="*",
			help="""generated data by a site id. It will be create only one site id.
			[use] -s 1 or  --sid=1
			[options] -s 1,2,3 or not
			[default: %default]""")

		parser.add_option("-g", "--groups",
			action="store",
			type="str",
			dest="groups",
			nargs=1,
			default="*",
			help="""set processing groups
			[use] -g closedBeta or openBeta or closedBeta,openBeta or None
			[options] closedBeta, openBeta or ETC
			[default: %default]""")

		parser.add_option("-p", "--period",
			action="store",
			dest="period",
			type="str",
			nargs=2,
			default=None,
			help="""[optional] data collecting period
			[use] -p 2015-07-01_00:00:00 2015-07-01_23:59:59""")

		parser.add_option("-D", "--device_protocol",
			action="store",
			dest="deviceProtocol",
			default=None,
			help="""select protocol of the device on tajo
			[use] -D edm3_100,edm3_201
			[options] edm3_100, edm3_201
			[default: %default]""")

		parser.add_option("-j", "--job",
			action="store",
			dest="job",
			default='*',
			help="""set processing job
			[use] -j META or USAGE
			[options] META, META
			[default: %default]""")

		parser.add_option("--REMOVE",
			action="store",
			default=None,
			dest="remove",
			help="""use this option remove the nilm data in DB
			[use] --REMOVE=meta,usage ...
			[options] appliance, meta, router, usage, all(*)
			[default: %default]""")

		parser.add_option("-P", "--USAGE_PERIOD",
			action="store",
			dest="usagePeriod",
			type="str",
			default="daily",
			help="""[optional] nilm analysis period
			[use] -P hourly or -P daily
			[default: %default]""")

		parser.add_option("--RAW_DATA",
			action="store_true",
			default=False,
			dest="onlyRawdata",
			help="""use this option it will be get only NILM_raw data.
			[use] --RAW_DATA
			[options] --RAW_DATA or None
			[default: %default""")

		options, args = parser.parse_args()
		self._vaildOptions(options, args)

	def _vaildOptions(self, options, args):
		optVaildator = OptionValidator(options, args)
		self.userOptions = optVaildator.doCheckOptions()

	def getUserOption(self):
		print "-" * 50
		for optKey in self.userOptions:
			print '- %s : %s' %(optKey.ljust(15), str(self.userOptions[optKey]))
		print "-" * 50

		return self.userOptions


class OptionValidator:
	def __init__(self, options, args):
		self._userOptions = self._setUserOptions(options, args)

	def _setUserOptions(self, options, args):
		user_options = {}
		if options.sids != None:
			user_options['sids'] = options.sids.split(',')
		if options.groups != None:
			user_options['groups'] = options.groups.split(',')
		if options.job != None:
			user_options['job'] = options.job.split(',')
		if options.period != None:
			user_options['period'] = options.period
		if options.remove != None:
			user_options['remove'] = options.remove.split(',')
		if options.onlyRawdata != None:
			user_options['onlyRawdata'] = options.onlyRawdata
		if options.usagePeriod != None:
			user_options['usagePeriod'] = options.usagePeriod
		return user_options

	def doCheckOptions(self):
		userOptions = {}
		userOptions['sids'] = self._checkSiteId()
		userOptions['dids'] = ['*']
		userOptions['gids'] = self._checkGroupId()
		userOptions['job'] = self._checkJob()
		startTS, endTS, userInputPeriod = self._checkPeriod()
		userOptions['startTS'] = startTS
		userOptions['endTS'] = endTS
		userOptions['userInputPeriod'] = userInputPeriod
		userOptions['onlyRawdata'] = self._checkCollectingRawDataMode(userOptions)
		userOptions['usagePeriod'] = self._checkUsagePeriod()
		userOptions['remove'] = self._checkRemove()
		return userOptions

	def _checkSiteId(self):
		tarSids = []
		sids = self._userOptions.get('sids')
		def isNumber(string):
			try:
				int(string)
				return True
			except ValueError:
				return False

		for sid in sids:
			if isNumber(sid):
				pass
			else:
				if sid == '*':
					return ['*']
				else:
					print "# Wrong site ids in the site id. Device id will be integer number or '*'."
					sys.exit(1)
		return [int(sid) for sid in sids]

	def _checkGroupId(self):
		tarGids = []
		gids = self._userOptions.get('groups')

		if not gids:
			print "# Wrong group ids. Check your options."
			sys.exit(1)

		for gid in gids:
			if gid == '*':
				return ['*']
			else:
				tarGids.append(gid)
		return tarGids

	def _checkPeriod(self):
		def _checkUsagePeriod(period):
			if period == 'hourly':
				startTS, endTS = getHourlyDatetime()
				return startTS, endTS
			elif period == 'daily':
				startTS, endTS = getDailyDatetime()
				return startTS, endTS
			else:
				return None, None

		def _checkUserPeriod(period):
			if self._userOptions.get('remove'):
				return 0, 0
			if not period or not len(period) == 2:
				return None, None
			else:
				startDT = period[0]
				endDT = period[1]
				startTS, endTS = getPeriodTS(startDT, endDT)
				return startTS, endTS

		def _error():
			print "# Wrong timestamp format. check your time range formats."
			sys.exit(1)

		period = self._userOptions.get('period')
		print period
		if period:
			startTS, endTS = _checkUserPeriod(period)
			userInputPeriod = True
		else:
			period = self._userOptions.get('usagePeriod')
			startTS, endTS = _checkUsagePeriod(period)
			userInputPeriod = False

		if not startTS or not endTS:
			_error()

		if startTS > endTS:
			_error()
		return startTS, endTS, userInputPeriod

	def _checkUsagePeriod(self):
		usagePeriod = self._userOptions.get('usagePeriod')
		if usagePeriod == 'hourly' or usagePeriod == 'daily':
			return usagePeriod
		else:
			print """# Wrong usage period. (You have to use one such as 'hourly' or 'daily'"""
			sys.exit(1)

	def _checkJob(self):
		tarJobs = []
		jobs = self._userOptions.get('job')

		if not jobs	:
			print """# Wrong job request. (You have to use one such as 'META', 'USAGE' or None = * )"""
			sys.exit(1)

		for job in jobs:
			job = job.lower()
			if job == '*':
				return [job]
			else:
				tarJobs.append(job)
		return tarJobs

	def _checkRemove(self):
		REMOVE_OPTIONS = ['appliance', 'meta', 'router', 'vfeeder', 'all', '*']
		options = self._userOptions.get('remove')

		if not options:
			return None

		options = list(set(options))
		if 'vfeeder' in options or 'all' in options or '*' in options:
			return ['vfeeder']

		sids = self._checkSiteId()
		if '*' in sids or len(sids) == 0 or len(sids) >1:
			print "# Wrong remove options. You have to use -s/--sids options."
			sys.exit(1)

		for option in options:
			if not option in REMOVE_OPTIONS:
				print "# Wrong remove options."
				sys.exit(1)
		return options

	def _checkCollectingRawDataMode(self, userOptions):
		isOnlyRawData = self._userOptions.get('onlyRawdata')
		if isOnlyRawData:
			sids = [int(sid) for sid in self._userOptions.get('sids')]
			userOptions['sids'] = sids
			return isOnlyRawData
		return isOnlyRawData

	def _checkUsagePeriod(self):
		usagePeriod = self._userOptions.get('usagePeriod')
		if usagePeriod == 'hourly' or usagePeriod == 'daily':
			return usagePeriod
		else:
			self._logger.warn("""# Wrong usage period. (You have to use one such as 'hourly' or 'daily'""")
			sys.exit(1)


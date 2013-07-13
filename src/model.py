# coding=utf-8

"""
The MIT License

Copyright (c) 2013 Mustafa İlhan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from google.appengine.api import memcache
from google.appengine.ext import db
from globals import Globals
import logging
import math
import time

class Trend(db.Model):
    name = db.StringProperty()
    woeid = db.IntegerProperty()
    timestamp = db.IntegerProperty()
    time = db.IntegerProperty()

class Error(db.Model):
    msg = db.StringProperty()
    timestamp = db.IntegerProperty()

def getTrends(woeid, startTimestamp, endTimestamp=0):
    """ get trends on specific timestamp or between timestamps """
    
    trends = []
    offset = 0
    
    if endTimestamp == 0:
        endTimestamp = startTimestamp + Globals._10_MINUTES
    
    while True:
        logging.info("getTrends(), woeid= %s, startTimestamp= %s, endTimestamp= %s, offset= %s", woeid, startTimestamp, endTimestamp, offset)
        fetchedTrends = Trend.all().filter("timestamp >=", startTimestamp).filter("timestamp <", endTimestamp).filter("woeid =", woeid).fetch(limit=Globals.DEFAULT_LIMIT, offset=offset)
        trends.extend(fetchedTrends)
        if len(fetchedTrends) != Globals.DEFAULT_LIMIT:
            break
        offset += Globals.DEFAULT_LIMIT
    return trends

def getLastestTrends(history, woeid):
    """ get lastest trends """
    
    expireTime = 0
    if history == 'ld':
        # last day
        expireTime = Globals._1_DAY
    elif history == 'lw':
        # last week
        expireTime = Globals._1_WEEK
    else:
        # last month
        expireTime = Globals._1_MONTH
    
    # Set start and end timestamp
    endTimestamp = int(math.floor(time.time()))
    startTimestamp = endTimestamp - expireTime 
    
    """ 
    Even if you search last day there are more than one thousand result 
    and datastore read operation is costly. Therefore caching is very important.
    
    1- Get cachedResult
    2- Compare start & end date and get results between our start & end date
    3- Get trends that are not previosuly
    4- Merge the results and cache again.
    """
    key = 'trends-' + history + "-" + str(woeid)
    cachedTrends = memcache.get(key)  # @UndefinedVariable
    if cachedTrends is not None and len(cachedTrends) > 0 and cachedTrends[-1].timestamp >= startTimestamp:
        for index, trend in enumerate(cachedTrends):
            if trend.timestamp >= startTimestamp:
                cachedTrends = cachedTrends[index:]
                break;
        
        startTimestamp = cachedTrends[-1].timestamp + 1
        logging.info("start changed from: %s, to: %s", startTimestamp, (cachedTrends[-1].timestamp + 1))
        
    else:
        cachedTrends = []
    
    newTrends = sorted(getTrends(woeid, startTimestamp, endTimestamp=endTimestamp), key=lambda trend: trend.timestamp)
    trends = cachedTrends + newTrends
    memcache.set(key=key, value=trends, time=expireTime)  # @UndefinedVariable
    
    logging.info("start: %s, end: %s", startTimestamp, endTimestamp)
    logging.info("key %s, cachedTrends: %s, newTrends: %s, allTrends: %s", key, len(cachedTrends), len(newTrends), len(trends))
    
    return trends

def mergeAndSortTrends(trends):
    mergedList = []
    for t in trends:
        found = False
        for m in mergedList:
            if t.name == m.name:
                m.time += t.time
                found = True
                break
        if not found:
            mergedList.append(t)
    
    return sorted(mergedList, key=lambda trend: trend.time, reverse=True)


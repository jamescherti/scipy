"""
:author: Pierre Gerard-Marchant
:contact: pierregm_at_uga_dot_edu
:version: $Id: core.py 59 2006-12-22 23:58:11Z backtopop $
"""
__author__ = "Pierre GF Gerard-Marchant ($Author: backtopop $)"
__version__ = '1.0'
__revision__ = "$Revision: 59 $"
__date__     = '$Date: 2006-12-22 18:58:11 -0500 (Fri, 22 Dec 2006) $'

import datetime
import itertools
import warnings


import numpy
from numpy import bool_, float_, int_, object_
from numpy import ndarray
import numpy.core.numeric as numeric
import numpy.core.fromnumeric as fromnumeric

import maskedarray as MA
#reload(MA)

import tscore as corelib
#reload(corelib)
from tscore import isDateType

#from corelib import fmtFreq, freqToType
import mx.DateTime as mxD
from mx.DateTime.Parser import DateFromString as mxDFromString


import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(name)-15s %(levelname)s %(message)s',)
daflog = logging.getLogger('darray_from')
dalog = logging.getLogger('DateArray')

#TODO: - it's possible to change the freq on the fly, e.g. mydateD.freq = 'A'
#TODO:   ...We can prevent that by making freq a readonly property, or call dateOf
#TODO:   ...or decide it's OK
#TODO: - Do we still need dateOf, or should we call cseries.convert instead ?
#TODO: - It'd be really nice if  cseries.convert could accpt an array, 
#TODO:   ...that way, we could call it instead of looping in asfreq
    
secondlyOriginDate = mxD.Date(1980) - mxD.DateTimeDeltaFrom(seconds=1)
minutelyOriginDate = mxD.Date(1980) - mxD.DateTimeDeltaFrom(minute=1)
hourlyOriginDate = mxD.Date(1980) - mxD.DateTimeDeltaFrom(hour=1)

#####---------------------------------------------------------------------------
#---- --- Date Exceptions ---
#####---------------------------------------------------------------------------
class DateError(Exception):
    """Defines a generic DateArrayError."""
    def __init__ (self, args=None):
        "Create an exception"
        Exception.__init__(self)
        self.args = args
    def __str__(self):
        "Calculate the string representation"
        return str(self.args)
    __repr__ = __str__
    
class InsufficientDateError(DateError):
    """Defines the exception raised when there is not enough information 
    to create a Date object."""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Insufficient parameters given to create a date at the given frequency"
        DateError.__init__(self, msg)
        
class FrequencyDateError(DateError):
    """Defines the exception raised when the frequencies are incompatible."""
    def __init__(self, msg, freql=None, freqr=None):
        msg += " : Incompatible frequencies!"
        if not (freql is None or freqr is None):
            msg += " (%s<>%s)" % (freql, freqr)
        DateError.__init__(self, msg)
        
class ArithmeticDateError(DateError):
    """Defines the exception raised when dates are used in arithmetic expressions."""
    def __init__(self, msg=''):
        msg += " Cannot use dates for arithmetics!"
        DateError.__init__(self, msg)

#####---------------------------------------------------------------------------
#---- --- Date Class ---
#####---------------------------------------------------------------------------

class Date:
    """Defines a Date object, as the combination of a date and a frequency.
    Several options are available to construct a Date object explicitly:

    - Give appropriate values to the `year`, `month`, `day`, `quarter`, `hours`, 
      `minutes`, `seconds` arguments.
      
      >>> td.Date(freq='Q',year=2004,quarter=3)
      >>> td.Date(freq='D',year=2001,month=1,day=1)
      
    - Use the `string` keyword. This method calls the `mx.DateTime.Parser`
      submodule, more information is available in its documentation.
      
      >>> ts.Date('D', '2007-01-01')
      
    - Use the `mxDate` keyword with an existing mx.DateTime.DateTime object, or 
      even a datetime.datetime object.
      
      >>> td.Date('D', mxDate=mx.DateTime.now())
      >>> td.Date('D', mxDate=datetime.datetime.now())
      """
    def __init__(self, freq, year=None, month=None, day=None, quarter=None, 
                 hours=None, minutes=None, seconds=None, 
                 mxDate=None, value=None, string=None):
        
        if hasattr(freq, 'freq'):
            self.freq = corelib.fmtFreq(freq.freq)
        else:
            self.freq = corelib.fmtFreq(freq)
        self.type = corelib.freqToType(self.freq)
        
        if value is not None:
            if self.freq == 'A':
                self.mxDate = mxD.Date(value, -1, -1)
            elif self.freq == 'B':
                value -= 1
                self.mxDate = mxD.DateTimeFromAbsDays(value + (value//5)*7 - (value//5)*5)
            elif self.freq in ['D','U']:
                self.mxDate = mxD.DateTimeFromAbsDays(value-1)
            elif self.freq == 'H':
                self.mxDate = hourlyOriginDate + mxD.DateTimeDeltaFrom(hours=value)
            elif self.freq == 'M':
                self.mxDate = mxD.Date(0) + \
                              mxD.RelativeDateTime(months=value-1, day=-1)
            elif self.freq == 'Q':
                self.mxDate = mxD.Date(0) + \
                              mxD.RelativeDateTime(years=(value // 4), 
                                                   month=((value * 3) % 12), day=-1)
            elif self.freq == 'S':
                self.mxDate = secondlyOriginDate + mxD.DateTimeDeltaFromSeconds(value)
            elif self.freq == 'T':
                self.mxDate = minutelyOriginDate + mxD.DateTimeDeltaFrom(minutes=value)
            elif self.freq == 'W':
                self.mxDate = mxD.Date(0) + \
                              mxD.RelativeDateTime(weeks=value-5./7-1)
        
        elif string is not None:
            self.mxDate = mxDFromString(string)  
            
        elif mxDate is not None:
            if isinstance(mxDate, datetime.datetime):
                mxDate = mxD.strptime(mxDate.isoformat()[:19], "%Y-%m-%dT%H:%M:%S")
            self.mxDate = mxDate
            
        else:
            # First, some basic checks.....
            if year is None:
                raise InsufficientDateError            
            if self.freq in ('B', 'D', 'W'):
                if month is None or day is None: 
                    raise InsufficientDateError
            elif self.freq == 'M':
                if month is None: 
                    raise InsufficientDateError
                day = -1
            elif self.freq == 'Q':
                if quarter is None: 
                    raise InsufficientDateError
                month = quarter * 3
                day = -1
            elif self.freq == 'A':
                month = -1
                day = -1
            elif self.freq == 'S':
                if month is None or day is None or seconds is None: 
                    raise InsufficientDateError
                
            if self.freq in ['A','B','D','M','Q','W']:
                self.mxDate = mxD.Date(year, month, day)
                if self.freq == 'B':
                    if self.mxDate.day_of_week in [5,6]:
                        raise ValueError("Weekend passed as business day")
            elif self.freq in ['H','S','T']:
                if not hours:
                    if not minutes:
                        if not seconds:
                            hours = 0
                        else:
                            hours = seconds//3600
                    else:
                        hours = minutes // 60
                if not minutes:
                    if not seconds:
                        minutes = 0
                    else:
                        minutes = (seconds-hours*3600)//60
                if not seconds:
                    seconds = 0
                else:
                    seconds = seconds % 60
                self.mxDate = mxD.Date(year, month, day, hours, minutes, seconds)     
        self.value = self.__value()
    # FIXME: Shall we set them as properties ?
    def day(self):          
        "Returns the day of month."
        return self.mxDate.day
    def day_of_week(self):  
        "Returns the day of week."
        return self.mxDate.day_of_week
    def day_of_year(self):  
        "Returns the day of year."
        return self.mxDate.day_of_year
    def month(self):        
        "Returns the month."
        return self.mxDate.month
    def quarter(self):   
        "Returns the quarter."   
        return monthToQuarter(self.mxDate.month)
    def year(self):         
        "Returns the year."
        return self.mxDate.year
    def second(self):    
        "Returns the seconds."  
        return int(self.mxDate.second)
    def minute(self):     
        "Returns the minutes."  
        return int(self.mxDate.minute)
    def hour(self):         
        "Returns the hour."
        return int(self.mxDate.hour)
    def week(self):
        "Returns the week."
        return self.mxDate.iso_week[1]
 
    def __add__(self, other):
        if isinstance(other, Date):
            raise FrequencyDateError("Cannot add dates", self.freq, other.freq)
        return Date(freq=self.freq, value=int(self) + other)
    
    def __radd__(self, other): 
        return self+other
    
    def __sub__(self, other):
        if isinstance(other, Date):
            if self.freq != other.freq:
                raise FrequencyDateError("Cannot subtract dates", \
                                         self.freq, other.freq)
            else:
                return int(self) - int(other) 
        else:
            return self + (-1) * int(other)
    
    def __eq__(self, other):
        if not hasattr(other, 'freq'):
            return False
        elif self.freq != other.freq:
            raise FrequencyDateError("Cannot subtract dates", \
                                     self.freq, other.freq)
        return int(self) == int(other) 
    
    def __cmp__(self, other): 
        if not hasattr(other, 'freq'):
            return False
        elif self.freq != other.freq:
            raise FrequencyDateError("Cannot subtract dates", \
                                     self.freq, other.freq)
        return int(self)-int(other)    
        
    def __hash__(self): 
        return hash(int(self)) ^ hash(self.freq)
    
    def __int__(self):
        return self.value
    
    def __float__(self):
        return float(self.value)
    
    def __value(self):   
        "Converts the date to an integer, depending on the current frequency."
        # Annual .......
        if self.freq == 'A':
            val = int(self.mxDate.year)
        # Business days.
        elif self.freq == 'B':
            days = self.mxDate.absdate
            weeks = days // 7
            val = int((weeks*5) + (days - weeks*7))
        # Daily/undefined
        elif self.freq in ['D', 'U']:
            val = self.mxDate.absdate
        # Hourly........
        elif self.freq == 'H':
            val = int((self.mxDate - hourlyOriginDate).hours)
        # Monthly.......
        elif self.freq == 'M':
            val = self.mxDate.year*12 + self.mxDate.month
        # Quarterly.....
        elif self.freq == 'Q':
            val = int(self.mxDate.year*4 + self.mxDate.month/3)
        # Secondly......
        elif self.freq == 'S':
            val = int((self.mxDate - secondlyOriginDate).seconds)
        # Minutely......
        elif self.freq == 'T':
            val = int((self.mxDate - minutelyOriginDate).minutes)
        # Weekly........
        elif self.freq == 'W':
            val = int(self.mxDate.year*365.25/7.-1) + self.mxDate.iso_week[1]
        return val
    #......................................................
    def default_fmtstr(self):
        "Defines the default formats for printing Dates."
        if self.freq == "A":
            fmt =  "%Y"
        elif self.freq in ("B","D"):
            fmt =  "%d-%b-%y"
        elif self.freq == "M":
            fmt =  "%b-%Y"
        elif self.freq == "Q":
            fmt =  "%YQ%q"
        elif self.freq in ("H","S","T"):
            fmt =  "%d-%b-%Y %H:%M:%S"
        elif self.freq == "W":
            fmt =  "%YW%W"
        else:
            fmt = "%d-%b-%y"
        return fmt
        
    def strfmt(self, fmt):
        "Formats the date"
        qFmt = fmt.replace("%q", "XXXX")
        tmpStr = self.mxDate.strftime(qFmt)
        return tmpStr.replace("XXXX", str(self.quarter()))
            
    def __str__(self):
        return self.strfmt(self.default_fmtstr())

    def __repr__(self): 
        return "<%s : %s>" % (str(self.freq), str(self))
    #......................................................
    def toordinal(self):
        "Returns the date as an ordinal."
        return self.mxDate.absdays

    def fromordinal(self, ordinal):
        "Returns the date as an ordinal."
        return Date(self.freq, mxDate=mxD.DateTimeFromAbsDays(ordinal))
    
    def tostring(self):
        "Returns the date as a string."
        return str(self)
    
    def toobject(self):
        "Returns the date as itself."
        return self
    
    def asfreq(self, toFreq, relation='before'):
        """Converts the date to a new frequency."""
        return dateOf(self, toFreq, relation)
    
    def isvalid(self):
        "Returns whether the DateArray is valid: no missing/duplicated dates."
        # A date is always valid by itself, but we need the object to support the function
        # when we're working with singletons.
        return True
    
#####---------------------------------------------------------------------------
#---- --- Functions ---
#####---------------------------------------------------------------------------
def monthToQuarter(monthNum):
    """Returns the quarter corresponding to the month `monthnum`.
    For example, December is the 4th quarter, Januray the first."""
    return int((monthNum-1)/3)+1

def thisday(freq):
    "Returns today's date, at the given frequency `freq`."
    freq = corelib.fmtFreq(freq)
    tempDate = mxD.now()
    # if it is Saturday or Sunday currently, freq==B, then we want to use Friday
    if freq == 'B' and tempDate.day_of_week >= 5:
        tempDate -= (tempDate.day_of_week - 4)
    if freq in ('B','D','H','S','T','W'):
        return Date(freq, mxDate=tempDate)
    elif freq == 'M':
        return Date(freq, year=tempDate.year, month=tempDate.month)
    elif freq == 'Q':
        return Date(freq, year=tempDate.year, quarter=monthToQuarter(tempDate.month))
    elif freq == 'A':
        return Date(freq, year=tempDate.year)
today = thisday

def prevbusday(day_end_hour=18, day_end_min=0):
    "Returns the previous business day."
    tempDate = mxD.localtime()
    dateNum = tempDate.hour + float(tempDate.minute)/60
    checkNum = day_end_hour + float(day_end_min)/60
    if dateNum < checkNum: 
        return thisday('B') - 1
    else: 
        return thisday('B')
                
def dateOf(date, toFreq, relation="BEFORE"):
    """Returns a date converted to another frequency `toFreq`, according to the
    relation `relation` ."""
    toFreq = corelib.fmtFreq(toFreq)
    _rel = relation.upper()[0]
    if _rel not in ['B', 'A']:
        msg = "Invalid relation '%s': Should be in ['before', 'after']"
        raise ValueError, msg % relation
    elif _rel == 'B':
        before = True
    else:
        before = False

    if not isDateType(date):
        raise DateError, "Date should be a valid Date instance!"

    if date.freq == toFreq:
        return date
    # Convert to annual ....................
    elif toFreq == 'A':
        return Date(freq='A', year=date.year())
    # Convert to quarterly .................
    elif toFreq == 'Q':
        if date.freq == 'A':
            if before: 
                return Date(freq='A', year=date.year(), quarter=1)
            else: 
                return Date(freq='A', year=date.year(), quarter=4)
        else:
            return Date(freq='Q', year=date.year(), quarter=date.quarter())
    # Convert to monthly....................
    elif toFreq == 'M':
        if date.freq == 'A':
            if before: 
                return Date(freq='M', year=date.year(), month=1)
            else: 
                return Date(freq='M', year=date.year(), month=12)
        elif date.freq == 'Q':
            if before: 
                return dateOf(date-1, 'M', "AFTER")+1
            else: 
                return Date(freq='M', year=date.year(), month=date.month())
        else:
            return Date(freq='M', year=date.year(), month=date.month())
    # Convert to weekly ....................
    elif toFreq == 'W':
        if date.freq == 'A':
            if before: 
                return Date(freq='W', year=date.year(), month=1, day=1)
            else: 
                return Date(freq='W', year=date.year(), month=12, day=-1)
        elif date.freq in ['Q','M']:
            if before: 
                return dateOf(date-1, 'W', "AFTER")+1
            else: 
                return Date(freq='W', year=date.year(), month=date.month())
        else:
            val = date.weeks() + int(date.year()*365.25/7.-1)
            return Date(freq='W', value=val)
    # Convert to business days..............
    elif toFreq == 'B':
        if date.freq in ['A','Q','M','W']:
            if before: 
                return dateOf(dateOf(date, 'D'), 'B', "AFTER")
            else: 
                return dateOf(dateOf(date, 'D', "AFTER"), 'B', "BEFORE")
        elif date.freq == 'D':
            # BEFORE result: preceeding Friday if date is a weekend, same day otherwise
            # AFTER result: following Monday if date is a weekend, same day otherwise
            tempDate = date.mxDate
            if before:
                if tempDate.day_of_week >= 5: 
                    tempDate -= (tempDate.day_of_week - 4)
            else:
                if tempDate.day_of_week >= 5: 
                    tempDate += 7 - tempDate.day_of_week
            return Date(freq='B', mxDate=tempDate)
        else: 
            if before: 
                return dateOf(dateOf(date, 'D'), 'B', "BEFORE")
            else: 
                return dateOf(dateOf(date, 'D'), 'B', "AFTER")
    # Convert to day .......................
    elif toFreq == 'D':
        # ...from annual
        if date.freq == 'A':
            if before: 
                return Date(freq='D', year=date.year(), month=1, day=1)
            else: 
                return Date(freq='D', year=date.year(), month=12, day=31) 
        # ...from quarter
        elif date.freq == 'Q':
            if before: 
                return dateOf(date-1, 'D', "AFTER")+1
            else: 
                return Date(freq='D', year=date.year(), month=date.month(), 
                            day=date.day())
        # ...from month
        elif date.freq == 'M':
            if before:
                return Date(freq='D', year=date.year(), month=date.month(), day=1)
            else:
                (mm,yy) = (date.month(), date.year())
                if date.month() == 12:
                    (mm, yy) = (1, yy + 1)
                else:
                    mm = mm + 1
                return Date('D', year=yy, month=mm, day=1)-1
        # ...from week
        elif date.freq == 'W':
            if before:
                return Date(freq='D', year=date.year(), month=date.month(), 
                            day=date.day())
            else:
                ndate = date + 1 
                return Date(freq='D', year=ndate.year(), month=ndate.month(), 
                            day=ndate.day()) 
        # ...from a lower freq
        else:
            return Date('D', year=date.year(), month=date.month(), day=date.day())  
    #Convert to hour........................
    elif toFreq == 'H':
        if date.freq in ['A','Q','M','W']:
            if before: 
                return dateOf(dateOf(date, 'D', "BEFORE"), 'H', "BEFORE")
            else: 
                return dateOf(dateOf(date, 'D', "AFTER"), 'H', "AFTER")
        if date.freq in ['B','D']:
            if before: 
                return Date(freq='H', year=date.year(), month=date.month(), 
                            day=date.day(), hours=0)
            else: 
                return Date(freq='H', year=date.year(), month=date.month(), 
                            day=date.day(), hours=23)
        else: 
            return Date(freq='H', year=date.year(), month=date.month(), 
                        day=date.day(), hours=date.hour())
    #Convert to second......................
    elif toFreq == 'T':
        if date.freq in ['A','Q','M','W']:
            if before: 
                return dateOf(dateOf(date, 'D', "BEFORE"), 'T', "BEFORE")
            else: 
                return dateOf(dateOf(date, 'D', "AFTER"), 'T', "AFTER")
        elif date.freq in ['B','D','H']:
            if before: 
                return Date(freq='T', year=date.year(), month=date.month(), 
                            day=date.day(), minutes=0)
            else: 
                return Date(freq='T', year=date.year(), month=date.month(), 
                            day=date.day(), minutes=24*60-1)
        else:
            return Date(freq='H', year=date.year(), month=date.month(), 
                        day=date.day(), hours=date.hour(), minutes=date.minute())
    #Convert to minute......................
    elif toFreq == 'S':
        if date.freq in ['A','Q','M','W']:
            if before: 
                return dateOf(dateOf(date, 'D', "BEFORE"), 'S', "BEFORE")
            else: 
                return dateOf(dateOf(date, 'D', "AFTER"), 'S', "AFTER")
        elif date.freq in ['B','D']:
            if before: 
                return Date(freq='S', year=date.year(), month=date.month(), 
                            day=date.day(), seconds=0)
            else: 
                return Date(freq='S', year=date.year(), month=date.month(), 
                            day=date.day(), seconds=24*60*60-1)
            
def isDate(data):
    "Returns whether `data` is an instance of Date."
    return isinstance(data, Date)

            
#####---------------------------------------------------------------------------
#---- --- DateArray ---
#####--------------------------------------------------------------------------- 
ufunc_dateOK = ['add','subtract',
                'equal','not_equal','less','less_equal', 'greater','greater_equal',
                'isnan']

class DateArray(ndarray):  
    """Defines a ndarray of dates, as ordinals.
    
When viewed globally (array-wise), DateArray is an array of integers.
When viewed element-wise, DateArray is a sequence of dates.
For example, a test such as :
>>> DateArray(...) = value
will be valid only if value is an integer, not a Date
However, a loop such as :
>>> for d in DateArray(...):
accesses the array element by element. Therefore, `d` is a Date object.    
    """
    def __new__(cls, dates=None, freq='U', copy=False):
        #dalog.info("__new__ received %s [%i]" % (type(dates), numpy.size(dates)))
        if isinstance(dates, DateArray):
            #dalog.info("__new__ sends %s as %s" % (type(dates), cls))
            cls.__defaultfreq = dates.freq
            if not copy:
                return dates.view(cls)
            return dates.copy().view(cls)
        else:
            _dates = numeric.asarray(dates, dtype=int_)
            if copy:
                _dates = _dates.copy()
            #dalog.info("__new__ sends %s as %s" % (type(_dates), cls))
            if freq is None:
                freq = 'U'
            cls.__defaultfreq = corelib.fmtFreq(freq)
            (cls.__toobj, cls.__toord, cls.__tostr) = (None, None, None)
            (cls.__steps, cls.__full, cls.__hasdups) = (None, None, None)
            return _dates.view(cls)
    
    def __array_wrap__(self, obj, context=None):
        if context is None:
            return self
        elif context[0].__name__ not in ufunc_dateOK:
            raise ArithmeticDateError, "(function %s)" % context[0].__name__
    
    def __array_finalize__(self, obj):
        #dalog.info("__array_finalize__ received %s" % type(obj))
        if hasattr(obj, 'freq'):
            self.freq = obj.freq
        else:
            self.freq = self.__defaultfreq
        #dalog.info("__array_finalize__ sends %s" % type(self))
    
    def __getitem__(self, index):
        #dalog.info("__getitem__ got  index %s (%s)"%(index, type(index)))
        if isDateType(index):
            index = self.find_dates(index)
        elif numeric.asarray(index).dtype.kind == 'O':
            try:
                index = self.find_dates(index)       
            except AttributeError:
                pass     
        r = ndarray.__getitem__(self, index)
        if r.size == 1:
            # Only one element, and it's not a scalar: we have a DateArray of size 1
            if len(r.shape) > 0:
                r = r.item()
            return Date(self.freq, value=r)
        else:
            return r
        
    def __repr__(self):
        return ndarray.__repr__(self)
    #......................................................
    @property
    def years(self):
        "Returns the years."
        return numeric.asarray([d.year() for d in self], dtype=int_)
    @property
    def months(self):
        "Returns the months."
        return numeric.asarray([d.month() for d in self], dtype=int_)
    @property
    def day_of_year(self):
        "Returns the days of years."
        return numeric.asarray([d.day_of_year() for d in self], dtype=int_)
    yeardays = day_of_year
    @property
    def day_of_week(self):
        "Returns the days of week."
        return numeric.asarray([d.day_of_week() for d in self], dtype=int_)
    #.... Conversion methods ....................
#    def toobject(self):
#        "Converts the dates from ordinals to Date objects."
#        # Note: we better try to cache the result
#        if self.__toobj is None:
##            toobj = numeric.empty(self.size, dtype=object_)
##            toobj[:] = [Date(self.freq, value=d) for d in self]
##            self.__toobj = toobj
#            self.__toobj = self
#        return self.__toobj
    #
    def tovalue(self):
        "Converts the dates to integer values."
        return numeric.asarray(self)
    #
    def toordinal(self):
        "Converts the dates from values to ordinals."
        # Note: we better try to cache the result
        if self.__toord is None:
#            diter = (Date(self.freq, value=d).toordinal() for d in self)
            diter = (d.toordinal() for d in self)
            toord = numeric.fromiter(diter, dtype=float_)
            self.__toord = toord
        return self.__toord
    #
    def tostring(self):
        "Converts the dates to strings."
        # Note: we better cache the result
        if self.__tostr is None:
            firststr = str(self[0])
            if self.size > 0:
                ncharsize = len(firststr)
                tostr = numpy.fromiter((str(d) for d in self),
                                        dtype='|S%i' % ncharsize)
            else:
                tostr = firststr
            self.__tostr = tostr
        return self.__tostr
    #
    def asfreq(self, freq=None):
        "Converts the dates to another frequency."
        # Note: As we define a new object, we don't need caching
        if freq is None:
            return self
        freq = corelib.fmtFreq(freq)
        if freq == self.freq:
            return self        
        if self.isvalid():
            new = numeric.arange(self.size, dtype=int_)
            new += self[0].asfreq(freq).value
        else:
            new = numpy.fromiter((d.asfreq(freq).value for d in self),
                                 dtype=float_)
        return DateArray(new, freq=freq)
    #......................................................
    def find_dates(self, *dates):
        "Returns the indices corresponding to given dates, as an array."
        ifreq = self.freq
        c = numpy.zeros(self.shape, bool_)
        for d in corelib.flatargs(*dates):
            if d.freq != ifreq:
                d = d.asfreq(ifreq)
            c += (self == d.value)
        c = c.nonzero()
        if fromnumeric.size(c) == 0:
            raise ValueError, "Date out of bounds!"
        return c  
    def date_to_index(self, date):
        "Returns the index corresponding to one given date, as an integer."
        if self.isvalid():
            index = date.value - self[0].value
            if index < 0 or index > self.size:
                raise ValueError, "Date out of bounds!"
            return index
        else:
            index_asarray = (self == date.value).nonzero()
            if fromnumeric.size(index_asarray) == 0:
                raise ValueError, "Date out of bounds!" 
            return index_asarray[0][0]
    #......................................................        
    def get_steps(self):
        """Returns the time steps between consecutive dates.
    The timesteps have the same unit as the frequency of the series."""
        if self.freq == 'U':
            warnings.warn("Undefined frequency: assuming daily!")
        if self.__steps is None:
            steps = numeric.asarray(numpy.diff(self))
            if steps.size > 0:
                if self.__full is None:
                    self.__full = (steps.max() == 1)
                if self.__hasdups is None:
                    self.__hasdups = (steps.min() == 0)
            else:
                self.__full = True
                self.__hasdups = False
            self.__steps = steps
        return self.__steps
    
    def has_missing_dates(self):
        "Returns whether the DateArray have missing dates."
        if self.__full is None:
            steps = self.get_steps()
        return not(self.__full)
    
    def isfull(self):
        "Returns whether the DateArray has no missing dates."
        if self.__full is None:
            steps = self.get_steps()
        return self.__full
    
    def has_duplicated_dates(self):
        "Returns whether the DateArray has duplicated dates."
        if self.__hasdups is None:
            steps = self.get_steps()
        return self.__hasdups
    
    def isvalid(self):
        "Returns whether the DateArray is valid: no missing/duplicated dates."
        return  (self.isfull() and not self.has_duplicated_dates())
    #......................................................
class _datearithmetics(object):
    """Defines a wrapper for arithmetic methods.
Instead of directly calling a ufunc, the corresponding method of  the `array._data` 
object is called instead.
If `asdates` is True, a DateArray object is returned , else a regular ndarray
is returned.
    """
    def __init__ (self, methodname, asdates=True):
        """
:Parameters:
    - `methodname` (String) : Method name.
        """
        self.methodname = methodname
        self._asdates = asdates
        self.__doc__ = getattr(methodname, '__doc__')
        self.obj = None
        #dalog.info('__datearithmetics got method %s' % methodname)
    #
    def __get__(self, obj, objtype=None):
        self.obj = obj
        return self
    #
    def __call__ (self, other, *args, **kwargs):
        "Execute the call behavior."
        instance = self.obj
        freq = instance.freq
        if 'context' not in kwargs:
            kwargs['context'] = 'DateOK'
        #dalog.info('__datearithmetics got other %s' % type(other))
        method = getattr(super(DateArray,instance), self.methodname)
        if isinstance(other, DateArray):
            if other.freq != freq:
                raise FrequencyDateError("Cannot operate on dates", \
                                         freq, other.freq)
#            other = 
        elif isDateType(other):
            if other.freq != freq:
                raise FrequencyDateError("Cannot operate on dates", \
                                         freq, other.freq)
            other = other.value
            #dalog.info('__datearithmetics got other %s' % type(other))
        elif isinstance(other, ndarray):
            if other.dtype.kind not in ['i','f']:
                raise ArithmeticDateError
        if self._asdates:
            return instance.__class__(method(other, *args), 
                                      freq=freq)
        else:
            return method(other, *args)
#............................
DateArray.__add__ = _datearithmetics('__add__', asdates=True)
DateArray.__radd__ = _datearithmetics('__add__', asdates=True)
DateArray.__sub__ = _datearithmetics('__sub__', asdates=True)
DateArray.__rsub__ = _datearithmetics('__rsub__', asdates=True)
DateArray.__le__ = _datearithmetics('__le__', asdates=False)
DateArray.__lt__ = _datearithmetics('__lt__', asdates=False)
DateArray.__ge__ = _datearithmetics('__ge__', asdates=False)
DateArray.__gt__ = _datearithmetics('__gt__', asdates=False)
DateArray.__eq__ = _datearithmetics('__eq__', asdates=False)
DateArray.__ne__ = _datearithmetics('__ne__', asdates=False)

#####---------------------------------------------------------------------------
#---- --- DateArray functions ---
#####---------------------------------------------------------------------------  
def isDateArray(a):
    "Tests whether an array is a DateArray object."
    return isinstance(a,DateArray)

def guess_freq(dates):
    """Tries to estimate the frequency of a list of dates, by checking the steps
    between consecutive dates The steps should be in days.
    Returns a frequency code (alpha character)."""
    ddif = numeric.asarray(numpy.diff(dates))
    ddif.sort()
    if ddif[0] == ddif[-1] == 1.:
        fcode = 'D'
    elif (ddif[0] == 1.) and (ddif[-1] == 3.):
        fcode = 'B'
    elif (ddif[0] > 3.) and  (ddif[-1] == 7.):
        fcode = 'W'
    elif (ddif[0] >= 28.) and (ddif[-1] <= 31.):
        fcode = 'M'
    elif (ddif[0] >= 90.) and (ddif[-1] <= 92.):
        fcode = 'Q'
    elif (ddif[0] >= 365.) and (ddif[-1] <= 366.):
        fcode = 'A'
    elif numpy.abs(24.*ddif[0] - 1) <= 1e-5 and \
         numpy.abs(24.*ddif[-1] - 1) <= 1e-5:
        fcode = 'H'
    elif numpy.abs(1440.*ddif[0] - 1) <= 1e-5 and \
         numpy.abs(1440.*ddif[-1] - 1) <= 1e-5:
        fcode = 'T'
    elif numpy.abs(86400.*ddif[0] - 1) <= 1e-5 and \
         numpy.abs(86400.*ddif[-1] - 1) <= 1e-5:
        fcode = 'S'
    else:
        warnings.warn("Unable to estimate the frequency! %.3f<>%.3f" %\
                      (ddif[0], ddif[-1]))
        fcode = 'U'
    return fcode


def _listparser(dlist, freq=None):
    "Constructs a DateArray from a list."
    dlist = numeric.asarray(dlist)
    dlist.sort()
    # Case #1: dates as strings .................
    if dlist.dtype.kind == 'S':
        #...construct a list of ordinals
        ords = numpy.fromiter((mxDFromString(s).absdays for s in dlist),
                               float_)
        ords += 1
        #...try to guess the frequency
        if freq is None:
            freq = guess_freq(ords)
        #...construct a list of dates
        dates = [Date(freq, string=s) for s in dlist]
    # Case #2: dates as numbers .................
    elif dlist.dtype.kind in ['i','f']:
        #...hopefully, they are values
        if freq is None:
            freq = guess_freq(dlist)
        dates = dlist
    # Case #3: dates as objects .................
    elif dlist.dtype.kind == 'O':
        template = dlist[0]
        #...as Date objects
        if isDateType(template):
            dates = numpy.fromiter((d.value for d in dlist), float_)
        #...as mx.DateTime objects
        elif hasattr(template,'absdays'):
            # no freq given: try to guess it from absdays
            if freq is None:
                ords = numpy.fromiter((s.absdays for s in dlist), float_)
                ords += 1
                freq = guess_freq(ords)
            dates = [Date(freq, mxDate=m) for m in dlist]
        #...as datetime objects
        elif hasattr(dlist[0], 'toordinal'):
            ords = numpy.fromiter((d.toordinal() for d in dlist), float_)
            if freq is None:
                freq = guess_freq(ords)
            dates = [Date(freq, mxDate=mxD.DateTimeFromAbsDays(a)) for a in ords]
    #
    result = DateArray(dates, freq)
    return result


def date_array(dlist=None, start_date=None, end_date=None, length=None, 
               include_last=True, freq=None):
    """Constructs a DateArray from:
    - a starting date and either an ending date or a given length.
    - a list of dates.
    """
    freq = corelib.fmtFreq(freq)
    # Case #1: we have a list ...................
    if dlist is not None:
        # Already a DateArray....................
        if isinstance(dlist, DateArray):
            if freq != dlist.freq:
                return dlist.asfreq(freq)
            else:
                return dlist
        return _listparser(dlist, freq)
    # Case #2: we have a starting date ..........
    if start_date is None:
        raise InsufficientDateError
    if not isDateType(start_date):
        raise DateError, "Starting date should be a valid Date instance!"
    # Check if we have an end_date
    if end_date is None:
        if length is None:
            raise ValueError,"No length precised!"
    else:
        assert(isDateType(end_date),
               "Starting date should be a valid Date instance!")
        length = end_date - start_date
        if include_last:
            length += 1
#    dlist = [(start_date+i).value for i in range(length)]
    dlist = numeric.arange(length, dtype=int_)
    dlist += start_date.value
    if freq is None:
        freq = start_date.freq
    return DateArray(dlist, freq=freq)
datearray = date_array

def date_array_fromlist(dlist, freq=None):
    "Constructs a DateArray from a list of dates."
    return date_array(dlist=dlist, freq=freq)

def date_array_fromrange(start_date, end_date=None, length=None, 
                         include_last=True, freq=None):
    """Constructs a DateArray from a starting date and either an ending date or 
    a length."""
    return date_array(start_date=start_date, end_date=end_date, 
                      length=length, include_last=include_last, freq=freq)    

#####---------------------------------------------------------------------------
#---- --- Definition of functions from the corresponding methods ---
#####---------------------------------------------------------------------------
class _frommethod(object):
    """Defines functions from existing MaskedArray methods.
:ivar _methodname (String): Name of the method to transform.
    """
    def __init__(self, methodname):
        self._methodname = methodname
        self.__doc__ = self.getdoc()
    def getdoc(self):
        "Returns the doc of the function (from the doc of the method)."
        try:
            return getattr(DateArray, self._methodname).__doc__
        except:
            return "???"
    #
    def __call__(self, caller, *args, **params):
        if hasattr(caller, self._methodname):
            method = getattr(caller, self._methodname)
            # If method is not callable, it's a property, and don't call it
            if hasattr(method, '__call__'):
                return method.__call__(*args, **params)
            return method
        method = getattr(fromnumeric.asarray(caller), self._methodname)
        try:
            return method(*args, **params)
        except SystemError:
            return getattr(numpy,self._methodname).__call__(caller, *args, **params)
#............................
day_of_week = _frommethod('day_of_week')
day_of_year = _frommethod('day_of_year')
year = _frommethod('year')
quarter = _frommethod('quarter')
month = _frommethod('month')
day = _frommethod('day')
hour = _frommethod('hour')
minute = _frommethod('minute')
second = _frommethod('second')


################################################################################
if __name__ == '__main__':
#    from maskedarray.testutils import assert_equal
    import datetime
    if 1:
        # get the last day of this year, at daily frequency
        dLastDayOfYear = dateOf(thisday('A'),'D','AFTER')
    if 0:
        # get the first day of this year, at business frequency
        bFirstDayOfYear = dateOf(thisday('A'),'B','BEFORE')
        # get the last day of the previous quarter, business frequency
        bLastDayOfLastQuarter = dateOf(thisday('Q')-1,'B','AFTER')
        # dateOf can also go from high frequency to low frequency. In this case, the third parameter has no impact
        aTrueValue = (thisday('Q') == dateOf(thisday('b'),'Q'))
        # dates of the same frequency can be subtracted (but not added obviously)
        numberOfBusinessDaysPassedThisYear = thisday('b') - bFirstDayOfYear
    
        # integers can be added/substracted to/from dates
        fiveDaysFromNow = thisday('d') + 5
    
        # get the previous business day, where business day is considered to
        # end at day_end_hour and day_end_min
        pbd = prevbusday(day_end_hour=18,day_end_min=0)
    
        # construct a date object explicitly
        myDateQ = Date(freq='Q',year=2004,quarter=3)
        myDateD = Date(freq='D',year=1985,month=10,day=4)
        
        #------------------------------------------------

import logging
import re
import warnings
import json
import requests

from datetime import datetime, date, timedelta

class ICalClient(object):

    _ICAL_URL = "https://calendar.google.com/calendar/ical/%s@group.calendar.google.com/%s/basic.ics"

    _LOG = logging.getLogger(__name__)

    def unfold_lines(self, physical_lines):
        current_line = ''
        for line in physical_lines:
            line = line.rstrip('\r')
            if not current_line:
                current_line = line
            elif line and line[0] in (' ', '\t'):
                current_line += line[1:]
            else:
                if len(current_line) > 0:
                    yield current_line
                current_line = line
        if current_line:
            yield current_line

    def tokenize_line(self, unfolded_lines):
        for line in unfolded_lines:
            pl = ContentLine.parse(line)
            if pl is not None:
                yield pl

    def parse(self, tokenized_lines):
        # tokenized_lines must be an iterator, so that Container.parse can consume/steal lines
        tokenized_lines = iter(tokenized_lines)
        for line in tokenized_lines:
            if line["name"] == 'BEGIN':
                return Container.parse(line["value"], tokenized_lines)

    def lines_to_container(self, lines):
        return self.parse(self.tokenize_line(self.unfold_lines(lines)))

    def string_to_container(self, txt):
        # unicode newlines are interpreted as such by str.splitlines(), but not by the ics standard
        # "A:abc\x85def".splitlines() => ['A:abc', 'def'] which is wrong
        return self.lines_to_container(re.split("\r?\n|\r", txt))

    @staticmethod
    def get_events(calendar_id, calendar_name):
        cal_url = ICalClient._ICAL_URL % (calendar_id, calendar_name)

        ICalClient._LOG.info("Fetching %s" % cal_url)
        url_get = requests.get(cal_url)
        url_get.raise_for_status()
        
        return ICalClient().string_to_container(url_get.text)

    @staticmethod
    def get_today():
        return datetime.today()

class CalendarItem(object):
    
    _ITEM_UID = "UID"
    _ITEM_TITLE = "SUMMARY"
    _ITEM_DESCRIPTION = "DESCRIPTION"
    _ITEM_START_DATE = "DTSTART;VALUE=DATE"
    _ITEM_START_DT = "DTSTART"
    _ITEM_LAST_MODIFIED = "LAST-MODIFIED"

    FORMATS = {
        8: "%Y%m%d",
        15: "%Y%m%dT%H%M%S"
    }

    def __init__(self, item):
        self.item = item
        self.uid = str(item[CalendarItem._ITEM_UID])[:2]
        self.title = item[CalendarItem._ITEM_TITLE]
        self.description = item[CalendarItem._ITEM_DESCRIPTION].encode("utf-8").decode("unicode_escape")

        if not self._parse_dt(CalendarItem._ITEM_START_DATE, "dt_start"):
            self._parse_dt(CalendarItem._ITEM_START_DT, "dt_start")
        self._parse_dt(CalendarItem._ITEM_LAST_MODIFIED, "dt_modified")

    def _parse_dt(self, name, var):
        if name in self.item:
            value = str(self.item[name]).translate({
                ord("/"): "",
                ord("-"): "",
                ord("Z"): "",
                ord("z"): ""})
            dt = datetime.strptime(value, self.FORMATS[len(value)])
            setattr(self, var, dt)

            return True

        setattr(self, var, None)  # Default value

        return False

    def get_dt_start(self):
        return self.dt_start.strftime("%Y-%m-%d")

    def is_valid(self):
        if self.dt_start is None:
            return False
        # enkel items nemen voor komende week
        dt_today = date.today()
        dt_min = dt_today + timedelta(days=7)
        dt_start = self.dt_start.date()

        return dt_start <= dt_min and dt_start >= dt_today

    def is_changed(self):
        if self.dt_modified is None:
            return False
        # is update wanneer aanpassing in laatste 6 uur gebeurd is
        dt_changed =  datetime.now() - timedelta(hours=5,minutes=59,seconds=59)
        # print("%s >= %s" % (self.dt_modified, dt_changed))
        return self.dt_modified >= dt_changed
 
    def __str__(self):
        return json.dumps({
            "title": self.title,
            "desc": self.description,
            "dt_start": self.dt_start.strftime("%d/%m/%Y") if self.dt_start is not None else "",
            "dt_modified": self.dt_modified.strftime("%d/%m/%Y %H:%M:%S") if self.dt_modified is not None else ""
        })

class ContentLine(object):

    _ITEMS = [
        "BEGIN", "END",
        CalendarItem._ITEM_START_DATE, CalendarItem._ITEM_START_DT, CalendarItem._ITEM_LAST_MODIFIED,
        CalendarItem._ITEM_UID, CalendarItem._ITEM_DESCRIPTION, CalendarItem._ITEM_TITLE
    ]
   
    @staticmethod
    def parse(line):
        """Parse a single iCalendar-formatted line into a ContentLine"""
        if "\n" in line or "\r" in line:
            raise ValueError("ContentLine can only contain escaped newlines")
        
        lp = str(line).split(":", 1)
        if lp[0] in ContentLine._ITEMS:
            return {"name": lp[0], "value": lp[1]}

        return None

class Container(object):
    
    @staticmethod
    def parse(name, tokenized_lines):
        items = []
        if not name.isupper():
            warnings.warn("Container 'BEGIN:%s' is not all-uppercase" % name)

        for line in tokenized_lines:
            if line["name"] == 'BEGIN':
                c = Container.parse(line["value"], tokenized_lines)
                if c is not None:
                    items.append(c)
            elif line["name"] == 'END':
                if line["value"].upper() != name.upper():
                    raise Exception(
                        "Expected END:{}, got END:{}".format(name, line["value"]))
                if not name.isupper():
                    warnings.warn("Container 'END:%s' is not all-uppercase" % name)
                break
            else:
                items.append(line["name"])
                items.append(line["value"])
        else:  # if break was not called
            raise Exception("Missing END:{}".format(name))
        
        # Only return events
        if name == "VEVENT":
            c = CalendarItem({ items[i]: items[i + 1] for i in range(0, len(items), 2) })
            if c.is_valid():
                print(c)
                return c
        elif name == "VCALENDAR":
            return items

        return None


import json

from datetime import datetime, date

class Schedule(object):

    _SCHEDULE_ITEMS = "calendarItems"
    
    @staticmethod
    def items(json):
        for i in json[Schedule._SCHEDULE_ITEMS]:
            s_item = ScheduleItem(i)
            if s_item.is_workout():
                yield s_item

class ScheduleItem(object):

    _SCHEDULE_TYPE_FIELD = "itemType"
    _SCHEDULE_WORKOUT_FIELD = "workoutId"
    _SCHEDULE_DATE_FIELD = "date"

    def __init__(self, item):
        self.item = item

    def is_workout(self):
        return str(self.item[ScheduleItem._SCHEDULE_TYPE_FIELD]).lower() == "workout"

    def extract_item_workout(self):
        return self.item[ScheduleItem._SCHEDULE_WORKOUT_FIELD]

    def extract_item_date(self):
        return self.item[ScheduleItem._SCHEDULE_DATE_FIELD]
import re
import json

class Step(object):

    _REGEX = re.compile("^\* (w|s|r|c)(?:(?: ([0-9]+?|[0-9]{2}:[0-9]{2})(k|m|t))(?: @(?:([0-9]{2,3}-[0-9]{2,3})|([0-9]{2}:[0-9]{2})))?)?")

    _WARMUP_STEP_TYPE = {
        "stepTypeId": 1,
        "stepTypeKey": "warmup",
    }

    _COOLDOWN_STEP_TYPE = {
        "stepTypeId": 2,
        "stepTypeKey": "cooldown",
    }

    _INTERVAL_STEP_TYPE = {
        "stepTypeId": 3,
        "stepTypeKey": "interval",
    }

    _RECOVERY_STEP_TYPE = {
        "stepTypeId": 4,
        "stepTypeKey": "recovery",
    }

    _REPEAT_STEP_TYPE = {
        "stepTypeId": 6,
        "stepTypeKey": "repeat",
    }

    _CONDITION_LAPBUTTON = {
        "conditionTypeId": 1,
        "conditionTypeKey": "lap.button"
    }

    _CONDITION_TIME = {
        "conditionTypeId": 2,
        "conditionTypeKey": "time"
    }

    _CONDITION_DISTANCE = {
        "conditionTypeId": 3,
        "conditionTypeKey": "distance"
    }

    _TARGET_NOTARGET_TYPE = {
        "workoutTargetTypeId": 1,
        "workoutTargetTypeKey": "no.target"
    }

    _TARGET_HR_TYPE = {
        "workoutTargetTypeId": 4,
        "workoutTargetTypeKey": "heart.rate.zone"
    }

    _TARGET_PACE_TYPE = {
        "workoutTargetTypeId": 6,
        "workoutTargetTypeKey": "pace.zone"
    }

    def __init__(self, groups):
        #print(json.dumps(groups))
        self.type = groups[0]
        self.end_value = groups[1]
        self.end_type = groups[2]
        self.target_bpm = groups[3]
        self.target_pace =groups[4]

    def create_step_json(self, step_order):
        return self._interval_step(step_order)

    def is_warmup(self):
        return self.type == "w"

    def is_recovery(self):
        return self.type == "r"

    def is_cooldown(self):
        return self.type == "c"

    @staticmethod
    def create_step(line):
        #print("%s" % line)

        g = Step._REGEX.match(line)
        if g and len(g.groups()) == 5:
            return Step(g.groups())

        raise Exception("Invalid step syntax for line < %s >" % line)

    def _interval_step(self, step_order, child_step_id = None):
        so = {
            "type": "ExecutableStepDTO",
            "stepOrder": step_order,
            "stepType": self._get_step_type(),
            "childStepId": child_step_id,
        }

        self._end_condition(so)
        self._target_type(so)

        return so
    
    def _get_step_type(self):
        if self.is_warmup():
            return self._WARMUP_STEP_TYPE
        if self.is_recovery():
            return self._RECOVERY_STEP_TYPE
        if self.is_cooldown():
            return self._COOLDOWN_STEP_TYPE

        return self._INTERVAL_STEP_TYPE

    def _end_condition(self, step):
        condition = value = None

        if self.end_type == "k":
            condition = self._CONDITION_DISTANCE
            value = self._end_condition_value() * 1000
        elif self.end_type == "m":
            condition = self._CONDITION_DISTANCE
            value = self._end_condition_value()
        elif self.end_type == "t":
            condition = self._CONDITION_TIME
            value = self._end_condition_value_time()

        if condition is None:
            condition = self._CONDITION_LAPBUTTON

        step["endCondition"] = condition
        step["endConditionValue"] = value

    def _end_condition_value(self):
        return int(self.end_value)

    def _end_condition_value_time(self):
        return self._strtime_to_seconds(self.end_value)

    def _target_type(self, step):
        target = value1 = value2 = None

        if self.target_bpm is not None:
            target = self._TARGET_HR_TYPE
            target_val = str(self.target_bpm).split("-")
            value1 = int(target_val[0])
            value2 = int(target_val[1])
        elif self.target_pace is not None:
            target = self._TARGET_PACE_TYPE
            target_seconds = self._strtime_to_seconds(self.target_pace)
            value1 = self._target_pace_one(target_seconds)
            value2 = self._target_pace_two(target_seconds)
        else:
            target = self._TARGET_NOTARGET_TYPE
                
        step["targetType"] = target
        step["targetValueOne"] = value1
        step["targetValueTwo"] = value2

    def _target_pace_one(self, sec):
        # Target pace is in m/s
        return 1000 / (sec - 3)

    def _target_pace_two(self, sec):
        # Target pace is in m/s
        return 1000 / (sec + 4)

    def _strtime_to_seconds(self, str_value):
        time = str(str_value).split(":")
        return (int(time[0]) * 60) + int(time[1])
import re
import json

class Step(object):

    _DEFAULT_PACE = "05:35"

    _REGEX = re.compile("^\* (w|s|r|c|x)(?:(?:(?: ([0-9]+?|[0-9]{2}:[0-9]{2})(k|m|t))|(?: ([1-9]) ([1-9][0-9]{0,1})))(?: @(?:([0-9]{2,3}-[0-9]{2,3})|([0-9]{2}:[0-9]{2})))?)?")

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

    def __init__(self, order_n, groups):
        # print(json.dumps(groups))
        # print("---")
        self.order = order_n
        self.type = groups[0]
        self.description = ""
        self.repeat_list = []
        self.end_value = groups[1]
        self.end_type = groups[2]
        self.step_repeat = groups[3]
        self.step_repeat_iterations = groups[4]
        self.target_bpm = groups[5]
        self.target_pace = groups[6]

    def create_step_json(self, child_step_id = None):
        if self.is_repeat():
            child_step_id = 0 if child_step_id is None else child_step_id
            return self._repeat_step(child_step_id + 1)
        # Default interval step
        return self._interval_step(child_step_id)

    def add_repeat_step(self, step):
        self.repeat_list.append(step)

    def generate_distance(self):
        self.est_dst = 0

        if self.is_repeat():
            for s in self.repeat_list:
                self.est_dst = self.est_dst + (s.generate_distance() * int(self.step_repeat_iterations))
        else:
            if self.end_type == "k":
                self.est_dst = self._end_condition_value() * 1000
            elif self.end_type == "m":
                self.est_dst = self._end_condition_value()
            elif self.end_type == "t":
                time = self._end_condition_value_time()
                if self.target_pace is None:
                    self.target_pace = Step._DEFAULT_PACE
                target_seconds = self._strtime_to_seconds(self.target_pace)
                self.est_dst = (time * 1000) / target_seconds
        
        return self.est_dst

    def generate_duration(self):
        self.est_dur = 0

        if self.is_repeat():
            for s in self.repeat_list:
                self.est_dur = self.est_dur + (s.generate_duration() * int(self.step_repeat_iterations))
        else:
            if self.end_type == "k" or self.end_type == "m":
                if self.target_pace is None:
                    self.target_pace = Step._DEFAULT_PACE
                target_seconds = self._strtime_to_seconds(self.target_pace)

                dst = self._end_condition_value()
                if self.end_type == "k":
                    dst = dst * 1000

                self.est_dur = target_seconds * dst / 1000
            elif self.end_type == "t":
                self.est_dur = self._end_condition_value_time()

        return self.est_dur

    def set_description(self, val):
        self.description = val

    def set_step_description(self, total_steps, n = None):
        n = self.order if n is None else n
        # Do not include it on last step
        if n != total_steps:
            self.description = "%d / %d" % (n, total_steps)
            if self.target_bpm is not None:
                target_val = str(self.target_bpm).split("-")
                avg_target = int((int(target_val[1]) + int(target_val[0])) / 2)
                self.description = self.description + " (%s)" % avg_target
            elif self.target_pace is not None:
                self.description = self.description + " (%s)" % self.target_pace

        if self.is_repeat():
            n = 1
            total = len(self.repeat_list)
            for r in self.repeat_list:
                # add description to nested steps
                r.set_step_description(total, n)
                # Increment to number of repeat
                n = n + 1
    
    def is_warmup(self):
        return self.type == "w"

    def is_recovery(self):
        return self.type == "r"

    def is_repeat(self):
        return self.type == "x"

    def get_repeat_number(self):
        return int(self.step_repeat)

    def is_cooldown(self):
        return self.type == "c"

    @staticmethod
    def create_step(step_data):
        # print("%s %s" % (step_data[1], step_data[0]))
        g = Step._REGEX.match(step_data[0])
        if g and len(g.groups()) == 7:
            return Step(step_data[1], g.groups())

        raise Exception("Invalid step syntax for line < %s >" % line)

    def _interval_step(self, child_step_id = None):
        so = {
            "type": "ExecutableStepDTO",
            "stepOrder": self.order,
            "stepType": self._get_step_type(),
            "childStepId": child_step_id,
            "description": self.description
        }

        self._end_condition(so)
        self._target_type(so)

        return so

    def _repeat_step(self, child_step_id):
        # Generate the repeat steps
        repeatSteps = []
        for rs in self.repeat_list:
            repeatSteps.append(rs.create_step_json(child_step_id))

        so = {
            "type": "RepeatGroupDTO",
            "stepOrder": self.order,
            "stepType": self._REPEAT_STEP_TYPE,
            "childStepId": child_step_id,
            "numberOfIterations": self.step_repeat_iterations,
            "smartRepeat": False,
            "workoutSteps": repeatSteps
        }

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

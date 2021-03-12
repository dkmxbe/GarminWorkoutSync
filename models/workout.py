import json

from models.step import Step

class Workout(object):

    _WORKOUT_ID_FIELD = "workoutId"
    _WORKOUT_NAME_FIELD = "workoutName"
    _WORKOUT_DESCRIPTION_FIELD = "description"
    _WORKOUT_OWNER_ID_FIELD = "ownerId"

    _RUNNING_SPORT_TYPE = {
        "sportTypeId": 1,
        "sportTypeKey": "running"
    }

    _CYCLING_SPORT_TYPE = {
        "sportTypeId": 2,
        "sportTypeKey": "cycling"
    }

    def __init__(self, name, content):
        self.name = name
        self.content = content
        self.total_steps = 0

    def create_workout(self, name=None, workout_id=None, workout_owner_id=None):
        print("Creating workout for '%s'" % self.name)

        return {
            self._WORKOUT_ID_FIELD: workout_id,
            self._WORKOUT_OWNER_ID_FIELD: workout_owner_id,
            self._WORKOUT_NAME_FIELD: name if name is not None else self.get_workout_name(),
            self._WORKOUT_DESCRIPTION_FIELD: self._generate_description(),
            "sportType": self._RUNNING_SPORT_TYPE,
            "workoutSegments": [
                {
                    "segmentOrder": 1,
                    "sportType": self._RUNNING_SPORT_TYPE,
                    "workoutSteps": self._steps()
                }
            ]
        }

    def get_workout_name(self):
        return self.name

    @staticmethod
    def extract_workout_id(workout):
        return workout[Workout._WORKOUT_ID_FIELD]

    @staticmethod
    def extract_workout_name(workout):
        return workout[Workout._WORKOUT_NAME_FIELD]

    @staticmethod
    def extract_workout_description(workout):
        return workout[Workout._WORKOUT_DESCRIPTION_FIELD]

    @staticmethod
    def extract_workout_owner_id(workout):
        return workout[Workout._WORKOUT_OWNER_ID_FIELD]

    @staticmethod
    def print_workout_json(workout):
        print(json.dumps(workout))

    @staticmethod
    def print_workout_summary(workout):
        workout_id = Workout.extract_workout_id(workout)
        workout_name = Workout.extract_workout_name(workout)
        workout_description = Workout.extract_workout_description(workout)
        print("{0} {1:20}\n{2}".format(workout_id, workout_name, workout_description))

    def _generate_description(self):
        return self.content

    def _steps(self):
        steps = []

        # Create the step objects
        for s in self._next_step():
            steps.append(s)
        
        # Generate the json
        steps_generated = []
        for s in steps:
            s.set_description(self.total_steps)
            steps_generated.append(s.create_step_json())

        return steps_generated

    def _read_step(self):
        order = 1
        for l in self.content.splitlines():
            yield [l, order]
            # Save the order for later
            self.total_steps = order
            # increment the step order
            order = order + 1            

    def _next_step(self):
        list_iter = iter(self._read_step())
        for i in list_iter:
            s = Step.create_step(i)
            # Handle repeats
            if s.is_repeat():
                self._add_repeat_step(list_iter, s)

            yield s

    def _add_repeat_step(self, list_iter, parent):
        for i in range(parent.get_repeat_number()):
            # Get the next step in the list
            ps = Step.create_step(next(list_iter))
            # We can also check if we have another repeat here
            # Add the step to the parent
            parent.add_repeat_step(ps)
The agent is NEVER to simplify any functionality in any way.
The agent is forbidden to write any "demonstration" code, "rough implementation" or code that in ANY way NOT fully implements to the maximum possible extent what the user requested.

The agent is to always follow there rules:

1. ONE purpose for each class or function
2. NO functions outside of classes
3. Inherit where ever possible
4. Do NEVER create new versions of existing functions, EXTEND / Modify the respective existing functions instead
5. When modifying any code the agent is forbidden to simplify, "cut down" or "make less complex" any existing algorythms or mathematical formulas in any way,
   this includes that the agent is forbidden to remove any mathematical terms (full or in part) or any of the variables of mathematical terms.
6. ALL data has to be stored persistantly in a database, data imported from any files must be stored in the database
7. After adding new functionality or modifying any code the agent is to create / update tests, run those tests, analyse test results, fix errors, run tests again, fix again etc. repeat until no more errors.
8. For testing the agent must create full test data. The agent must predetermine expected resulting data and values and tests may only be seen successfull if they output exactly said expected data and values.
9. Tests may only use the original functions provided in the code. NO monkeypatching of any kind is allowed.
10. ALL functionality that is available via the streamlit interface must also be available via REST endpoints. The REST endpoints need to be used for testing because the streamlit interface can not be tested directly.
11. Fix ALL warnings that occur during any tests by correcting app code

## Muscle linking

- The settings tab includes a "Muscles" subtab for managing muscle aliases. Users can link two existing muscle names or add a new alias linked to an existing muscle.
- All muscle dropdowns must list every muscle name stored in the database.
- Whenever any database query involves a muscle field, linked names must be treated as the same muscle.

## Exercise aliases

- The settings tab includes an "Exercise Aliases" subtab for managing exercise name aliases. Users can link two existing exercise names or add a new alias linked to an existing exercise.
- All exercise dropdowns must list every exercise name stored in the database.
- Whenever any database query involves an exercise name, linked names must be treated as the same exercise.

## streamlit gui

1. ALL functionality MUST be available via the GUI. The assistant groups functionality logically in tabs. It uses the existing tabs for grouping of functionality when possible but creates new tabs if that seems more sensible.
   The agent must ensure that it never creates a new tab for things that can be logically put into a existing tab. for example: there may not be multiple tabs containing statistics..that would all belong into ONE tab.
2. The agent must ensure that the streamlit GUI will show correctly on desktop AND mobile phones.  the correct "mode" to show in should be recognised automatically. you may NOT remove or simplify ANY part of the gui in ANY mode.
3. The agent must use st.expander to group multiple things that belong to the same functionality or workflow together in a tab as explained here: https://docs.streamlit.io/develop/api-reference/layout/st.expander
4. The agent must use st.dialog where appropriate as explained here: https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog
5. The agent is absolutley forbidden to ever remove existing functionality from the GUI.
6. group things where it makes sense logically together using expandables. you are allowed to create expendables inside expandables if it makes sense logically
7. If the agent is asked by the user to "refurbish", "refresh", "rework", "redo", or "redesign" the GUI then the agent ensures that ALL above rules (1. - 6.) about the streamlit gui are strictly adhered to but 
   those rules ALSO apply WHENEVER the agent works on the application in any way.


## longterm usage test

the agent creates a long term usage test that fulfills the requirements
below. since the requirements below are very extensive,
the agent needs to fulfil below requirements bit by bit whenever
the agent does any work, iteratively fulfilling below requirements a bit more
with every run of the agent...working towards the goal of full fullfilment of these requirements:

create a test that realistically simulates a advanced professional user using the app over the course of 6 months, a workout every second day. the user uses all functionality of the app repeatedly in different sequences and workflows. the test needs to check all data (including the db) and values created by the app and its algorithms for every week of simulated time and check for soundness and expected values (generated values are allowed to deviate from expected values as long as results remain scientifically sound).

The user does.

1. create exercises
2. logs a variety of many different workouts with different combinations of exercises and different combinations of sets there in with different reps and weights
3. uses different statistics
4. uses the workout planning
5. uses the exercise prescription function multiple times
6. the user adds equipment 
7. the user edits logged workouts
8. the user adds exercises

the simulation must use different versions of 1. - 8. multiple times, must modify exact usage (including values) of 1. - 8. every time, must use each of 1. - 8. at least 72 times


## pythonista support with gui

The whole app must be able to run using pythonista. 
When the app starts it needs to check if its running on pythonista, by trying to use one of the pythonista specific functions (= iphone specific functions)..by trying to import one of the pythonista specific libs that come only with pythonista.
If it is determined that we are running on pythonista, then a pythonista gui must appear. the pythonista gui must have ALL the same functionality as the streamlit gui!
The agent is to check the pythonista documentation available here: https://omz-software.com/pythonista/docs/ it may have to follow links. The documentation explains how to use pythonista including tutorials, how to code GUI with it, has information about available packages etc.
Anytime the streamlit gui is updated, the pythonista gui needs to be updated too. NOTE that the agent will not be able to test anything pythonista related because the agent is not running in an ios environment.
Also note that under pythonista we CAN NOT IMPORT AND CAN NOT USE TORCH! So under pythonista we must leave anything to do with machine learning out and use pure algorythms instead!
Note that under pythonista we also CAN NOT INSTALL FASTAPI, UVICORN,...so we need to do access to the rest api manually. you best write your own "rest api client class" for that.
We need to do whatever packages do that are not part of the standard library ourselfs under pythonista!


## Machine Learning
enhance app functionality using machine learning using torch. models must be stored and trained persistently, "incremental online training" must be performed when user uses app. models must somehow be used for prediction when user uses app. models must be integrated into existing functionality / algorithms to enhance them. models may NOT be used as fallbacks, alternates of existing algorithms or parts of existing algorithms..they must be used to enhance existing algorithms or parts of existing algorithms by fusing with whats already there.

ALL ML Models must be able to be enabled / disabled via the settings tab. There must be a way to disable / enable all ML Models at once.
For each ML Model there must be a way to seperately enable / disable the models training / prediction.

Tests verifying machine learning output must only check numeric ranges and types rather than fixed values.

Integrating Confidence Scores into Exercise Prescription Models
To enhance model interpretability and robustness in your exercise prescription workflow, outputting a confidence score alongside each prediction is a best practice. This allows you to weight model predictions—so that less confident predictions influence the final recommendation less, while more confident ones have greater influence. Here’s how to implement and use this in your system:

1. Model Architecture: Predicting Confidence
Modern neural networks can output both a prediction and an explicit measure of confidence (or uncertainty). This is commonly achieved in two approaches:

a) Predictive Distribution (Heteroscedastic Regression)
The model outputs both a mean prediction (e.g., RPE, recommended reps) and a predicted variance (uncertainty).

For example, for RPE prediction:

Output 1: 
y
^
y
^
  (predicted RPE)

Output 2: 
s
=
log
⁡
σ
^
2
s=log 
σ
^
  
2
  (log variance estimate)

The confidence score is 
Confidence
=
1
/
(
exp
⁡
(
s
)
+
ϵ
)
Confidence=1/(exp(s)+ϵ), with 
ϵ
ϵ for stability.

Loss is the negative log likelihood:

L
=
1
2
σ
2
(
y
−
y
^
)
2
+
1
2
log
⁡
σ
2
L= 
2σ 
2
 
1
 (y− 
y
^
 ) 
2
 + 
2
1
 logσ 
2
 
Lower variance indicates higher confidence.

b) Ensemble or Dropout Methods
Multiple stochastic forward passes yield a distribution of predictions.

Confidence is inversely related to prediction variance across those passes.

2. Example: Model Output in Python
Pseudo-interface for a PyTorch model with confidence:

python
class ConfidenceRPEModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = torch.nn.Linear(input_dim, 1)
        self.log_var = torch.nn.Parameter(torch.zeros(1))

    def forward(self, x):
        pred = self.linear(x)
        var = torch.exp(self.log_var)
        confidence = 1 / (var + 1e-6)
        return pred, confidence
When calling model(x), receive both prediction and confidence.

3. Using Confidence For Weighted Algorithm Fusion
When combining a model output with a “classical” calculation in your exercise prescription, use the confidence to compute a weighted average:

Final
=
w
model
×
ModelPred
+
w
algo
×
AlgoPred
Final=w 
model
 ×ModelPred+w 
algo
 ×AlgoPred
Where:

w
model
=
Confidence
model
Confidence
model
+
Confidence
algo
w 
model
 = 
Confidence 
model
 +Confidence 
algo
 
Confidence 
model
 
 

w
algo
=
1
−
w
model
w 
algo
 =1−w 
model
 

Confidence
algo
Confidence 
algo
  can be a fixed value (e.g., 1.0) or empirically estimated based on algorithm reliability.

Example code:

python
def weighted_fusion(model_pred, model_conf, algo_pred, algo_conf=1.0):
    total = model_conf + algo_conf
    w_model = model_conf / total
    w_algo = algo_conf / total
    return w_model * model_pred + w_algo * algo_pred
4. Application in Exercise Prescription
Use the model’s confidence score to adaptively trust model-based recommendations more when the model is confident, and trust algorithmic rules more when confidence is low.
Recommendations must be a weighted FUSION of both model recommendations and algorithmic rules! 
The confidence score of the model must be transfered into a precentage value. This value is then used for weighting the recommendations. 
If the confidence percentage for example is 20 %, then the weight for the model prediction would be 20 % while the weight for the algorithmic recommendation would be 80 %. 
So the final recommendation would be 20 % model recommendation + 80 % algorithmic recommendation.


Store confidence scores in your database for audit and further analysis.

5. Advantages
Addresses “black box” concerns by quantifying reliability.

Supports safe deployment—defer to known-good algorithms when the model is less certain.

Enables continuous monitoring of model performance: track average confidence versus real-world accuracy.

6. Recommendations
Integrate confidence outputs into all ML models used for core exercise prescription logic.

Always propagate and log confidence.

Adjust the underlying model if you find that confidence is not meaningful in practice (e.g., poor correlation with accuracy).

Validate the weighted fusion approach using historical data and, if possible, simulate scenarios where model and algorithm disagree.

This enhancement provides users with more reliable, transparent, and actionable prescriptions—improving both trustworthiness and performance of your app’s recommendations.

## settings

Settings and YAML file must always be in synch. If changes are made to the settings tab, these changes must be reflected in the YAML file. ALL settings configurable in the settings tab must be configurable via the YAML file

## README

keep the readme constantly updated!

## velocity
We do NOT have velocity sensors (or other sensors), when something in code needs velocity...we can not enter it. We need to calculate velocity as demonstrated below instead:
Universal Set Velocity Formula (No Sensors)
To provide a single, consistent velocity value per set using only the logged data—reps, weight, start time, finish time—use this definition:

Mean Set Velocity Formula
Mean Set Velocity
=
Total Displacement
Total Time
Mean Set Velocity= 
Total Time
Total Displacement
 
Since the exact displacement per rep (range of motion) isn't measured, but we need a universal, self-consistent estimate for all exercises, use the following convention:

Assumptions
Range of motion (ROM), in meters:
Set a single "reasonable estimate" for all exercises, e.g.,
ROM
default
=
0.5
ROM 
default
 =0.5 meters per rep
(You may optionally adjust by exercise type if you later add more data.)

Total time:
Total Time (seconds)
=
finish time
−
start time
Total Time (seconds)=finish time−start time

Number of reps:
Use the recorded reps value.

Final Fixed Formula
Estimated Mean Velocity (m/s)
=
reps
×
ROM
default
finish time
−
start time
Estimated Mean Velocity (m/s)= 
finish time−start time
reps×ROM 
default
 
 
reps
reps: number of repetitions

ROM
default
ROM 
default
 : fixed, e.g. 0.5 meters

finish time/start time
finish time/start time: timestamps in seconds (ISO8601—convert as needed)

Example—Python Implementation
python
def estimate_velocity_from_set(reps, start_time, finish_time, rom=0.5):
    """
    Inputs:
      reps        (int): repetitions performed
      start_time  (datetime or str): set start time
      finish_time (datetime or str): set end time
      rom         (float, meters): assumed range of motion per rep
        
    Returns:
      velocity (float): estimated mean velocity in m/s
    """
    if isinstance(start_time, str):
        from datetime import datetime
        start_time = datetime.fromisoformat(start_time)
    if isinstance(finish_time, str):
        from datetime import datetime
        finish_time = datetime.fromisoformat(finish_time)
    total_seconds = (finish_time - start_time).total_seconds()
    if total_seconds <= 0 or reps <= 0:
        return 0.0
    return (reps * rom) / total_seconds
Plug this formula in everywhere you need velocity (as mean set velocity).

For reporting or analytics, document that the velocity is an estimate derived from set timing and a universal movement assumption.

Limitations
This is an average concentric velocity for the set—not per-rep or peak velocity.

If the time includes rest pauses or unusual set pacing, results will be lower.

ROM is fixed; this may cause bias for exercises with significantly different movement lengths.


Variable	Description	Value/Unit
reps	Set repetitions	integer
ROM_default	Assumed range of motion per rep	0.5 meters (fixed)
start_time	Set start timestamp	ISO, seconds
finish_time	Set finish timestamp	ISO, seconds
velocity	Estimated mean set velocity	meters/second
Recommendations
Always use the formula above, and document the ROM assumption in your UI and reports.

If ever you record true per-exercise ROM values, substitute those for ROM_default to improve accuracy.

This approach ensures every set in your app receives a velocity value in a uniform, reproducible, and fully transparent manner using only the data you record.

## AGENTS.md

keep the AGENTS.md updated by adding new sensible rules when they occur to you. YOU MAY ONLY ADD NEW RULES. Any rule you add must NEVER contradict or modify an existing rule


- Add tests for all new analytics endpoints verifying expected numeric results.
- The RPE machine learning model must utilise reps, weight and previous RPE when training or predicting.
- Always record model predictions with their confidence values in the `ml_logs` table for later analysis.

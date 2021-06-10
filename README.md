# FMstimator

FMstimator approximates a feature model for a target commit based on the commit history of the respective project.
Starting from two feature models, it performs stepwise updates to the models to update them to the target commit.
In the end, both models are merged to create the final model.

The tool is located in the directory [src](src).


## Setup

First, setup the submodules.
```
git submodule init
git submodule update
```

Install the required packages with 
```
pip install -r requirements.txt
```
Install the pythonbindings of vara-feature.
Instructions can be found in their repository.
The submodule is set to a commit that contains fixes to make it work with this tool.


## Usage

FMstimator has four required arguments.
1. path to project git repository
2. path to first feature model
3. path to second feature model
4. commit reference of target commit

The feature models must adhere to the extended xml-format of feature models.
The target commit must be reachable over the first parents of the second feature model's commit.
Likewise, the commit that the first feature model corresponds to must be reachable over the first parents of the target commit.

Examples files can be found in the all projects under [eval](eval).
There are also [test repositories](src/test-repo-generation) with that test specific code changes.
The test repositories can be generated with 
```
./generateRepos.py <output folder>
```
`ansible.cfg`, `base_config.yml`, and `generateRepos.py` were initially supplied by the supervising chair.

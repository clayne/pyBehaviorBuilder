# pyBehaviorBuilder
Python factory to create havok behavior .xml files for skyrim

Example script:

With havok animation:
```
from BehaviorBuilder import BehaviorFile
example_behavior = BehaviorFile()
example_behavior.add_state(name="retract", animation_path="animations\\retract.hkx", looping=True)
example_behavior.add_state(name="extend", animation_path="animations\\extend.hkx")
example_behavior.connect_states(state1="retract",state2="extend",event="PlayExtend")
example_behavior.connect_states(state1="extend",state2="retract",event="PlayRetract")
example_behavior.add_wildcard(stateStr="retract", event="gotoRetract")
example_behavior.add_wildcard(stateStr="extend", event="gotoExtend")
example_behavior.export("OC_exampleBehavior.xml")
```

if instead using gamebryo animation:
```
from BehaviorBuilder import BehaviorFile
example_behavior = BehaviorFile()
example_behavior.add_state(name="retract", gamebryoanim=True)
example_behavior.add_state(name="extend", gamebryoanim=True)
example_behavior.connect_states(state1="retract",state2="extend",event="Extend")
example_behavior.connect_states(state1="extend",state2="retract",event="Retract")
example_behavior.add_wildcard(stateStr="retract", event="gotoRetract")
example_behavior.add_wildcard(stateStr="extend", event="gotoExtend")
example_behavior.export("OC_exampleBehavior.xml")
```

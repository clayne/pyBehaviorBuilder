#!/usr/bin/env python
# coding: utf-8
# BehaviorBuilder - code to build havok behavior files for animated static meshes for skyrim
# Copyright (C) 2021  OpheliaComplex

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import xml.etree.ElementTree as ET
import logging

logging.basicConfig(format='%(message)s')
log = logging.getLogger(__name__)


# Some sweet prettify commands from user Tatarize only using pure xml.etree.ElementTree (no minidom or lxml)
# https://stackoverflow.com/a/65808327
def _pretty_print(current, parent=None, index=-1, depth=0):
    for i, node in enumerate(current):
        _pretty_print(node, current, i, depth + 1)
    if parent is not None:
        if index == 0:
            parent.text = '\n' + ('\t' * depth)
        else:
            parent[index - 1].tail = '\n' + ('\t' * depth)
        if index == len(parent) - 1:
            current.tail = '\n' + ('\t' * (depth - 1))


def prettify_and_print(xml_obj, filepath):
    _pretty_print(xml_obj)
    with open(filepath, 'wb') as f:
        f.write(ET.tostring(xml_obj, encoding='ascii', method='xml', short_empty_elements=False))


class BehaviorFile:
    # Object counter, start at 51 - this is what I've seen in game files, also seen 49 - but whatever
    root_index = object_counter = 51

    # The header
    hkpackfile = ET.Element('hkpackfile')
    hkpackfile.set('classversion', '8')
    hkpackfile.set('contentsversion', 'hk_2010.2.0-r1')
    hkpackfile.set('toplevelobject', "#{:04d}".format(root_index))
    # The data element
    data = ET.SubElement(hkpackfile, 'hksection')
    data.set('name', '__data__')

    # the hkbBehaviorGraphStringData object, created on init but should be accessed later
    hkbBehaviorGraphStringData = None

    # hkbVariableValueSet, likely static
    hkbVariableValueSet = None

    # hkbBehaviorGraphData, created on init but should be updated with the hkbBehaviorGraphStringData object
    hkbBehaviorGraphData = None

    # wildcardtransitions hkbStateMachineTransitionInfoArray object
    # only created if wildcards are added
    wildcardtransitions = None

    # state counter
    nStates = 0
    # state list, tuple (name, state (hkbStateMachineStateInfo object))
    list_of_states = []

    # List of objects with their tag
    object_list = []

    def __init__(self):
        self.hkbBehaviorGraphStringData = hkbBehaviorGraphStringData(self)
        self.hkbVariableValueSet = hkbVariableValueSet(self)
        self.hkbBehaviorGraphData = hkbBehaviorGraphData(self)
        # also make a default transition effect
        self.blend_effect = hkbBlendingTransitionEffect(self)
        return

    def __call__(self):
        return self.data

    def _full_obj(self):
        return self

    def _OCinc(self):
        self.object_counter += 1

    def _OCnext(self):
        # increment and return as formatted
        self.object_counter += 1
        return "#{:04d}".format(self.object_counter)

    def add_state(self, name, animation_path="placeholder", looping=False, gamebryoanim=False, enterNotifyEvents="null",
                  exitNotifyEvents="null"):
        # minimum for adding a state is a:
        # actual state hkbStateMachineStateInfo containing at least:
        # a generator hkbClipGenerator/BGSGamebryoSequenceGenerator
        # a transitions hkbStateMachineTransitionInfoArray

        # the transitions, then the generator and finally the state
        assert isinstance(name, str)
        assert isinstance(animation_path, str)
        if not gamebryoanim and animation_path == "placeholder":
            log.warning(
                "If adding a .hkx animation state, the animation_path argument must be passed: 'animations\\<your anim name.hkx>")
            return
        # check that name is unique
        if self.list_of_states:
            for stateInfo, stateGenerator, stateTransitions, stateName in self.list_of_states:
                if stateName == name:
                    log.warning("a state with name " + name + " already in project, chose a unique name")
                    return

        # empty transitions
        transitions = hkbStateMachineTransitionInfoArray(BehaviorFileObj=self)
        # Generator with name and path to hkx i.e. animations\animname.hkx
        if not gamebryoanim:
            generator = hkbClipGenerator(self, name, animation_path, looping=looping)
        else:
            generator = BGSGamebryoSequenceGenerator(self, nifAnimName=name)

        # if enterNotifyEvents or exitNotifyEvents is not Null then a hkbStateMachineEventPropertyArray needs to be created
        if enterNotifyEvents != "null":
            enter_eventPropArray = hkbStateMachineEventPropertyArray(self, enterNotifyEvents)
        else:
            enter_eventPropArray = "null"

        if exitNotifyEvents != "null":
            exit_eventPropArray = hkbStateMachineEventPropertyArray(self, exitNotifyEvents)
        else:
            exit_eventPropArray = "null"

        # The state
        state = hkbStateMachineStateInfo(BehaviorFileObj=self,
                                         generator=generator,
                                         transitions=transitions,
                                         name=name,
                                         state_ID=self.nStates,
                                         enterNotifyEvents=enter_eventPropArray,
                                         exitNotifyEvents=exit_eventPropArray)
        # increment nStates and add this entry it to the state list
        self.nStates += 1
        self.list_of_states.append((state, generator, transitions, name))
        log.warning("added state " + name + " with state ID " + str(state.stateIdx) + " to project")

    def add_clip_trigger(self, state, event, relativeToEndOfClip=False, localTime=0.0):
        # Add a trigger (send an event) during the clip (animation) being played in a state
        assert isinstance(state, str)
        assert isinstance(event, str)
        assert isinstance(localTime, (float, int))
        assert isinstance(relativeToEndOfClip, bool)

        # Collect the state
        for stateInfo, stateGenerator, stateTransitions, stateName in self.list_of_states:
            if stateName == state:
                break
        else:
            log.warning("add_clip_trigger error, state " + state + " doesnt exist")

        if isinstance(stateGenerator, BGSGamebryoSequenceGenerator):
            raise TypeError("Cannot add clip triggers to BGSGamebryoSequenceGenerators. Manually add the clip trigger in the nif with text keys.")

        # Create a clip trigger array for this state, or collect it if it already exists
        clip_trigger = stateInfo.getOrCreateClipTriggerArray(self)

        # Similarly, get or create the event id
        event_ID = self.hkbBehaviorGraphStringData.getOrCreateEventID(BehaviorFileObj=self, event_name=event)

        # Add a trigger to it
        clip_trigger.add_trigger(localTime=localTime, EventID=event_ID, relativeToEndOfClip=relativeToEndOfClip)
        # update the generator
        stateGenerator.set_trigger(clip_trigger)

    def connect_states(self, state1, state2, event):
        # Add a transition from state1 into state2 upon receiving event
        # updates the hkbStateMachineTransitionInfoArray of state1 by
        # adding a transitions object entry pointing to the stateID of state2
        # first create the event if it doesn't exist in the hkbBehaviorGraphStringData
        assert isinstance(state1, str)
        assert isinstance(state2, str)
        assert isinstance(event, str)
        assert state1 != state2
        # update the hkbStateMachineTransitionInfoArray of state1
        # collect state1 and state2
        for stateInfo, stateGenerator, stateTransitions, stateName in self.list_of_states:
            if stateName == state1:
                break
        else:
            log.warning("connect_states error, state1 " + state1 + " doesnt exist")

        for stateInfo2, stateGenerator2, stateTransitions2, stateName2 in self.list_of_states:
            if stateName2 == state2:
                break
        else:
            log.warning("connect_states error, state2 " + state2 + " doesnt exist")

        # if event exists, collect ID, else create and get ID
        eventIndex = self.hkbBehaviorGraphStringData.getOrCreateEventID(BehaviorFileObj=self, event_name=event)

        # add_transition(self, eventId, toStateId, transition="null", condition="null", wildcard=False)
        stateTransitions.add_transition(eventIdIdx=eventIndex, toStateIdIdx=stateInfo2.stateIdx,
                                        transitionStr=self.blend_effect.tag)
        log.warning("added a transition from " + state1 + " to " + state2 + " (ID " + str(
            stateInfo2.stateIdx) + ") with event " + event)

    def add_wildcard(self, stateStr, event):
        assert isinstance(stateStr, str)
        assert isinstance(event, str)
        # add a wildcard transition to state upon receiving event
        # make sure the state exists
        for stateInfo, stateGenerator, stateTransitions, stateName in self.list_of_states:
            if stateName == stateStr:
                break
        else:
            log.warning("Add_wildcard error, state " + stateStr + " doesnt exist, create it first")
            return
        # create the event if it doesn't exist in the hkbBehaviorGraphStringData
        eventIndex = self.hkbBehaviorGraphStringData.getOrCreateEventID(BehaviorFileObj=self, event_name=event)
        # then create a hkbStateMachineTransitionInfoArray for the root generator if it doesn't have one already
        wildcardtransitionsOBJ = self.getOrCreatewildcardtransitions()
        # then add a transitions object pointing to the stateID of state
        wildcardtransitionsOBJ.add_transition(eventIdIdx=eventIndex, toStateIdIdx=stateInfo.stateIdx,
                                              transitionStr=self.blend_effect.tag, wildcard=True)
        log.warning("Added wildcard transition to state " + stateStr + " with event " + str(event))

    def getOrCreatewildcardtransitions(self):
        # Simply check if this has already been created, otherwise make it, then return the obj
        if self.wildcardtransitions is not None:
            return self.wildcardtransitions
        else:
            self.wildcardtransitions = hkbStateMachineTransitionInfoArray(self)
            return self.wildcardtransitions

    def __finalize(self):
        # add the main hkbStateMachine with all the states
        self.hkbStateMachineObj = hkbStateMachine(self)
        # add the states
        for stateInfo, stateGenerator, stateTransitions, stateName in self.list_of_states:
            self.hkbStateMachineObj.add_state(stateInfo)

        # add the hkbBehaviorGraph
        self.hkbBehaviorGraphObj = hkbBehaviorGraph(self)

        # add the final root container at the bottom
        # header
        hkobject = ET.SubElement(self.data, 'hkobject')
        hkobject.set('name', "#{:04d}".format(self.root_index))
        hkobject.set('class', 'hkRootLevelContainer')
        hkobject.set('signature', "0x2772c11e")
        # namedVariants
        namedVariants = ET.SubElement(hkobject, "hkparam")
        namedVariants.set("name", "namedVariants")
        namedVariants.set("numelements", "1")

        # namedVariantsobject
        namedVariantsObject = ET.SubElement(namedVariants, "hkobject")
        # name
        name = ET.SubElement(namedVariantsObject, "hkparam")
        name.set("name", "name")
        name.text = "hkbBehaviorGraph"
        # className
        className = ET.SubElement(namedVariantsObject, "hkparam")
        className.set("name", "className")
        className.text = "hkbBehaviorGraph"
        # variant
        variant = ET.SubElement(namedVariantsObject, "hkparam")
        variant.set("name", "variant")
        variant.text = self.hkbBehaviorGraphObj.tag

    def export(self, filepath):
        self.__finalize()
        prettify_and_print(self.hkpackfile, filepath)


class hkbBehaviorGraphData:
    tag = "MISSING"
    hkobject = None
    nEvents = 0

    def __init__(self, BehaviorFileObj):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbBehaviorGraphData')
        self.hkobject.set('signature', "0x95aca5d")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # attributeDefaults
        self.attributeDefaults = ET.SubElement(self.hkobject, 'hkparam')
        self.attributeDefaults.set("name", "attributeDefaults")
        self.attributeDefaults.set("numelements", str(0))
        # variableInfos
        self.variableInfos = ET.SubElement(self.hkobject, 'hkparam')
        self.variableInfos.set("name", "variableInfos")
        self.variableInfos.set("numelements", str(0))
        # characterPropertyInfos
        self.characterPropertyInfos = ET.SubElement(self.hkobject, 'hkparam')
        self.characterPropertyInfos.set("name", "characterPropertyInfos")
        self.characterPropertyInfos.set("numelements", str(0))
        # eventInfos
        self.eventInfos = ET.SubElement(self.hkobject, 'hkparam')
        self.eventInfos.set("name", "eventInfos")
        self.eventInfos.set("numelements", str(self.nEvents))
        # wordMinVariableValues
        self.wordMinVariableValues = ET.SubElement(self.hkobject, 'hkparam')
        self.wordMinVariableValues.set("name", "wordMinVariableValues")
        self.wordMinVariableValues.set("numelements", str(0))
        # wordMaxVariableValues
        self.wordMaxVariableValues = ET.SubElement(self.hkobject, 'hkparam')
        self.wordMaxVariableValues.set("name", "wordMaxVariableValues")
        self.wordMaxVariableValues.set("numelements", str(0))
        # variableInitialValues
        self.variableInitialValues = ET.SubElement(self.hkobject, 'hkparam')
        self.variableInitialValues.set("name", "variableInitialValues")
        self.variableInitialValues.text = BehaviorFileObj.hkbVariableValueSet.tag
        # stringData
        self.stringData = ET.SubElement(self.hkobject, 'hkparam')
        self.stringData.set("name", "stringData")
        self.stringData.text = BehaviorFileObj.hkbBehaviorGraphStringData.tag

    def add_event(self, flags=0):
        assert isinstance(flags, int)
        event_object = ET.SubElement(self.eventInfos, 'hkobject')
        event_flags = ET.SubElement(event_object, 'hkparam')
        event_flags.set("name", "flags")
        event_flags.text = str(flags)
        # add to internal counter, event_name_list and increase event counter
        self.nEvents += 1
        self.eventInfos.set("numelements", str(self.nEvents))


class hkbVariableValueSet:
    tag = "MISSING"
    hkobject = None
    nwordVariableValues = 0
    nquadVariableValues = 0
    nvariantVariableValues = 0

    def __init__(self, BehaviorFileObj):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbVariableValueSet')
        self.hkobject.set('signature', "0x27812d8d")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # wordVariableValues
        self.wordVariableValues = ET.SubElement(self.hkobject, 'hkparam')
        self.wordVariableValues.set("name", "wordVariableValues")
        self.wordVariableValues.set("numelements", str(self.nwordVariableValues))
        # quadVariableValues
        self.quadVariableValues = ET.SubElement(self.hkobject, 'hkparam')
        self.quadVariableValues.set("name", "quadVariableValues")
        self.quadVariableValues.set("numelements", str(self.nquadVariableValues))
        # variantVariableValues
        self.variantVariableValues = ET.SubElement(self.hkobject, 'hkparam')
        self.variantVariableValues.set("name", "variantVariableValues")
        self.variantVariableValues.set("numelements", str(self.nvariantVariableValues))


class hkbBehaviorGraphStringData:
    tag = "MISSING"
    nEvents = 0
    event_name_list = []
    nAttributes = 0
    nVariables = 0
    ncharacterPropertyNames = 0
    hkobject = None

    def __init__(self, BehaviorFileObj):
        assert isinstance(BehaviorFileObj, object)
        # assert BehaviorFileObj.__class__.__name__=="BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbBehaviorGraphStringData')
        self.hkobject.set('signature', "0xc713064e")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # eventNames
        self.eventNames = ET.SubElement(self.hkobject, 'hkparam')
        self.eventNames.set("name", "eventNames")
        self.eventNames.set("numelements", str(self.nEvents))
        # attributeNames
        self.attributeNames = ET.SubElement(self.hkobject, 'hkparam')
        self.attributeNames.set("name", "attributeNames")
        self.attributeNames.set("numelements", str(self.nAttributes))
        # variableNames
        self.variableNames = ET.SubElement(self.hkobject, 'hkparam')
        self.variableNames.set("name", "variableNames")
        self.variableNames.set("numelements", str(self.nVariables))
        # characterPropertyNames
        self.characterPropertyNames = ET.SubElement(self.hkobject, 'hkparam')
        self.characterPropertyNames.set("name", "characterPropertyNames")
        self.characterPropertyNames.set("numelements", str(self.ncharacterPropertyNames))

    def add_event(self, event_name):
        assert isinstance(event_name, str)
        if any([event_name == x for x in self.event_name_list]):
            raise "tried to add event with the same name as one already in hkbBehaviorGraphStringData"
        new_event = ET.SubElement(self.eventNames, 'hkcstring')
        new_event.text = event_name
        # add to internal counter, event_name_list and increase event counter
        self.nEvents += 1
        self.event_name_list.append(event_name)
        self.eventNames.set("numelements", str(self.nEvents))
        log.warning("created new event " + event_name)

    def get_eventID(self, event):
        assert isinstance(event, str)
        for eventIndex in range(0, len(self.event_name_list)):
            if self.event_name_list[eventIndex] == event:
                break
        else:
            raise "requested event that doesn't exist"
        return eventIndex

    def getOrCreateEventID(self, BehaviorFileObj, event_name):
        assert isinstance(event_name, str)
        assert isinstance(BehaviorFileObj, object)
        if event_name in self.event_name_list:
            return self.get_eventID(event_name)
        else:
            self.add_event(event_name)
            # also have to add a new intro to the hkbbehaviorgraphdata
            # ToDo flags might need to propagate here NOT IMPLEMENTED
            BehaviorFileObj.hkbBehaviorGraphData.add_event()
            return self.getOrCreateEventID(BehaviorFileObj, event_name)

    def add_variable(self, variable):
        # not implemented
        raise "not implemented"

    def add_characterProperty(self, characterProperty):
        # not implemented
        raise "not implemented"


class hkbBlendingTransitionEffect:
    tag = "MISSING"
    hkobject = None

    def __init__(self, BehaviorFileObj, name="ZeroDuration"):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        assert isinstance(name, str)
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbBlendingTransitionEffect')
        self.hkobject.set('signature', "0xfd8584fe")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # userData
        self.userData = ET.SubElement(self.hkobject, 'hkparam')
        self.userData.set("name", "userData")
        self.userData.text = name
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = "name"
        # comments
        self.hkobject.append(ET.Comment(' id SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' cloneState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' padNode SERIALIZE_IGNORED '))
        # selfTransitionMode
        self.selfTransitionMode = ET.SubElement(self.hkobject, 'hkparam')
        self.selfTransitionMode.set("name", "selfTransitionMode")
        self.selfTransitionMode.text = "SELF_TRANSITION_MODE_CONTINUE_IF_CYCLIC_BLEND_IF_ACYCLIC"
        # eventMode
        self.eventMode = ET.SubElement(self.hkobject, 'hkparam')
        self.eventMode.set("name", "eventMode")
        self.eventMode.text = "EVENT_MODE_DEFAULT"
        # comment
        self.hkobject.append(ET.Comment(' defaultEventMode SERIALIZE_IGNORED '))
        # duration
        self.duration = ET.SubElement(self.hkobject, 'hkparam')
        self.duration.set("name", "duration")
        self.duration.text = "{:.06f}".format(0)
        # toGeneratorStartTimeFraction
        self.toGeneratorStartTimeFraction = ET.SubElement(self.hkobject, 'hkparam')
        self.toGeneratorStartTimeFraction.set("name", "toGeneratorStartTimeFraction")
        self.toGeneratorStartTimeFraction.text = "{:.06f}".format(0)
        # flags
        self.flags = ET.SubElement(self.hkobject, 'hkparam')
        self.flags.set("name", "flags")
        self.flags.text = "0"
        # endMode
        self.endMode = ET.SubElement(self.hkobject, 'hkparam')
        self.endMode.set("name", "endMode")
        self.endMode.text = "END_MODE_NONE"
        # blendCurve
        self.blendCurve = ET.SubElement(self.hkobject, 'hkparam')
        self.blendCurve.set("name", "blendCurve")
        self.blendCurve.text = "BLEND_CURVE_SMOOTH"
        # comments
        self.hkobject.append(ET.Comment(' fromGenerator SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' toGenerator SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' characterPoseAtBeginningOfTransition SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' timeRemaining SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' timeInTransition SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' applySelfTransition SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' initializeCharacterPose SERIALIZE_IGNORED '))


class hkbStateMachineTransitionInfoArray:
    transitions = None
    numTransitions = 0
    tag = "MISSING"
    hkobject = None

    def __init__(self, BehaviorFileObj):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbStateMachineTransitionInfoArray')
        self.hkobject.set('signature', "0xe397b11e")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        self.transitions = ET.SubElement(self.hkobject, 'hkparam')
        self.transitions.set("name", "transitions")
        self.transitions.set("numelements", str(self.numTransitions))

    def add_transition(self, eventIdIdx, toStateIdIdx, transitionStr="null", conditionStr="null", wildcard=False):
        assert isinstance(eventIdIdx, int)
        assert isinstance(toStateIdIdx, int)
        # transitionsobject
        transitionsobject = ET.SubElement(self.transitions, "hkobject")
        # triggerInterval
        triggerInterval = ET.SubElement(transitionsobject, "hkparam")
        triggerInterval.set("name", "triggerInterval")
        # triggerintervalobject
        triggerintervalobject = ET.SubElement(triggerInterval, "hkobject")
        # enterEventId
        enterEventId = ET.SubElement(triggerintervalobject, "hkparam")
        enterEventId.set("name", "enterEventId")
        enterEventId.text = "-1"
        # exitEventId
        exitEventId = ET.SubElement(triggerintervalobject, "hkparam")
        exitEventId.set("name", "exitEventId")
        exitEventId.text = "-1"
        # enterTime
        enterTime = ET.SubElement(triggerintervalobject, "hkparam")
        enterTime.set("name", "enterTime")
        enterTime.text = "{:.06f}".format(0)
        # exitTime
        exitTime = ET.SubElement(triggerintervalobject, "hkparam")
        exitTime.set("name", "exitTime")
        exitTime.text = "{:.06f}".format(0)

        # transition
        transition = ET.SubElement(transitionsobject, "hkparam")
        transition.set("name", "transition")
        transition.text = transitionStr
        # condition
        condition = ET.SubElement(transitionsobject, "hkparam")
        condition.set("name", "condition")
        condition.text = conditionStr
        # eventId
        eventId = ET.SubElement(transitionsobject, "hkparam")
        eventId.set("name", "eventId")
        eventId.text = str(eventIdIdx)
        # toStateId
        toStateId = ET.SubElement(transitionsobject, "hkparam")
        toStateId.set("name", "toStateId")
        toStateId.text = str(toStateIdIdx)
        # fromNestedStateId
        fromNestedStateId = ET.SubElement(transitionsobject, "hkparam")
        fromNestedStateId.set("name", "fromNestedStateId")
        fromNestedStateId.text = "0"
        # toNestedStateId
        toNestedStateId = ET.SubElement(transitionsobject, "hkparam")
        toNestedStateId.set("name", "toNestedStateId")
        toNestedStateId.text = "0"
        # priority
        priority = ET.SubElement(transitionsobject, "hkparam")
        priority.set("name", "priority")
        priority.text = "0"
        # flags
        flags = ET.SubElement(transitionsobject, "hkparam")
        flags.set("name", "flags")
        if wildcard:
            flags.text = "FLAG_IS_LOCAL_WILDCARD|FLAG_DISABLE_CONDITION"
        else:
            flags.text = "FLAG_DISABLE_CONDITION"

        # update numelements
        self.numTransitions += 1
        self.transitions.set("numelements", str(self.numTransitions))


class hkbClipGenerator:
    tag = "MISSING"
    hkobject = None

    def __init__(self, BehaviorFileObj, name, anim_path, triggers="null", looping=False):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        assert (triggers.__class__.__name__ == "hkbClipTriggerArray" or (isinstance(triggers, str)))
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbClipGenerator')
        self.hkobject.set('signature', "0x333b85b9")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' cachedBindables SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' areBindablesCached SERIALIZE_IGNORED '))
        # userData
        self.userData = ET.SubElement(self.hkobject, 'hkparam')
        self.userData.set("name", "userData")
        self.userData.text = "0"
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = name
        # comments
        self.hkobject.append(ET.Comment(' id SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' cloneState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' padNode SERIALIZE_IGNORED '))
        # animationName
        self.animationName = ET.SubElement(self.hkobject, 'hkparam')
        self.animationName.set("name", "animationName")
        self.animationName.text = anim_path
        # triggers
        self.triggers = ET.SubElement(self.hkobject, 'hkparam')
        self.triggers.set("name", "triggers")
        if isinstance(triggers, str):
            self.triggers.text = triggers
        else:
            self.triggers.text = triggers.tag
        # cropStartAmountLocalTime
        self.cropStartAmountLocalTime = ET.SubElement(self.hkobject, 'hkparam')
        self.cropStartAmountLocalTime.set("name", "cropStartAmountLocalTime")
        self.cropStartAmountLocalTime.text = "{:.06f}".format(0)
        # cropEndAmountLocalTime
        self.cropEndAmountLocalTime = ET.SubElement(self.hkobject, 'hkparam')
        self.cropEndAmountLocalTime.set("name", "cropEndAmountLocalTime")
        self.cropEndAmountLocalTime.text = "{:.06f}".format(0)
        # startTime
        self.startTime = ET.SubElement(self.hkobject, 'hkparam')
        self.startTime.set("name", "startTime")
        self.startTime.text = "{:.06f}".format(0)
        # playbackSpeed
        self.playbackSpeed = ET.SubElement(self.hkobject, 'hkparam')
        self.playbackSpeed.set("name", "playbackSpeed")
        self.playbackSpeed.text = "{:.06f}".format(1)
        # enforcedDuration
        self.enforcedDuration = ET.SubElement(self.hkobject, 'hkparam')
        self.enforcedDuration.set("name", "enforcedDuration")
        self.enforcedDuration.text = "{:.06f}".format(0)
        # userControlledTimeFraction
        self.userControlledTimeFraction = ET.SubElement(self.hkobject, 'hkparam')
        self.userControlledTimeFraction.set("name", "userControlledTimeFraction")
        self.userControlledTimeFraction.text = "{:.06f}".format(0)
        # animationBindingIndex
        self.animationBindingIndex = ET.SubElement(self.hkobject, 'hkparam')
        self.animationBindingIndex.set("name", "animationBindingIndex")
        self.animationBindingIndex.text = "-1"
        # Setting the mode of the clip, see https://www.youtube.com/watch?v=ekQPKNLvSLs
        # Options here are:
        # MODE_SINGLE_PLAY
        # MODE_LOOPING
        # MODE_USER_CONTROLLED
        # MODE_PING_PONG
        # MODE_COUNT
        self.mode = ET.SubElement(self.hkobject, 'hkparam')
        self.mode.set("name", "mode")
        # some have MODE_USER_CONTROLLED but seems to behave similarly
        if looping:
            self.mode.text = "MODE_LOOPING"
        else:
            self.mode.text = "MODE_SINGLE_PLAY"
            # flags
        self.mode = ET.SubElement(self.hkobject, 'hkparam')
        self.mode.set("name", "flags")
        self.mode.text = "0"
        # a ton of comments
        self.hkobject.append(ET.Comment(' animDatas SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' animationControl SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' originalTriggers SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' mapperData SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' binding SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' mirroredAnimation SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' extractedMotion SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' echos SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' localTime SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' time SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' previousUserControlledTimeFraction SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' bufferSize SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' echoBufferSize SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' atEnd SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' ignoreStartTime SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' pingPongBackward SERIALIZE_IGNORED '))

    def set_trigger(self, trigger):
        assert (trigger.__class__.__name__ == "hkbClipTriggerArray")
        self.triggers.text = trigger.tag


class BGSGamebryoSequenceGenerator:
    tag = "MISSING"
    hkobject = None

    def __init__(self, BehaviorFileObj, nifAnimName="MISSING"):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        assert isinstance(nifAnimName, str)
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'BGSGamebryoSequenceGenerator')
        self.hkobject.set('signature', "0xc8df2d77")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' cachedBindables SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' areBindablesCached SERIALIZE_IGNORED '))
        # userData
        self.userData = ET.SubElement(self.hkobject, 'hkparam')
        self.userData.set("name", "userData")
        self.userData.text = "0"
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = nifAnimName + "Sequence"
        # comments
        self.hkobject.append(ET.Comment(' id SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' cloneState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' padNode SERIALIZE_IGNORED '))
        # pSequence
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "pSequence")
        self.name.text = nifAnimName
        # eBlendModeFunction
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "eBlendModeFunction")
        self.name.text = "BMF_NONE"
        # fPercent
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "fPercent")
        self.name.text = "{:.06f}".format(1)
        # comments
        self.hkobject.append(ET.Comment(' events SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' fTime SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' bDelayedActivate SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' bLooping SERIALIZE_IGNORED '))


class hkbStateMachineStateInfo:
    stateIdx = "MISSING"
    stateName = "MISSING"
    tag = "MISSING"
    hkobject = None
    hkbClipTriggerArray = None

    def __init__(self, BehaviorFileObj, generator, transitions, name, state_ID, enterNotifyEvents="null",
                 exitNotifyEvents="null"):
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        assert (
                    generator.__class__.__name__ == "hkbClipGenerator" or generator.__class__.__name__ == "BGSGamebryoSequenceGenerator")
        assert transitions.__class__.__name__ == "hkbStateMachineTransitionInfoArray"
        assert (exitNotifyEvents.__class__.__name__ == "hkbStateMachineEventPropertyArray" or (
                    isinstance(exitNotifyEvents, str) and exitNotifyEvents == "null"))
        assert (enterNotifyEvents.__class__.__name__ == "hkbStateMachineEventPropertyArray" or (
                    isinstance(enterNotifyEvents, str) and enterNotifyEvents == "null"))
        assert isinstance(name, str)
        assert isinstance(state_ID, int)
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbStateMachineStateInfo')
        self.hkobject.set('signature', "0xed7f9d0")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' cachedBindables SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' areBindablesCached SERIALIZE_IGNORED '))
        # listeners
        self.listeners = ET.SubElement(self.hkobject, 'hkparam')
        self.listeners.set("name", "listeners")
        self.listeners.set("numelements", "0")
        # enterNotifyEvents
        self.enterNotifyEvents = ET.SubElement(self.hkobject, 'hkparam')
        self.enterNotifyEvents.set("name", "enterNotifyEvents")
        if isinstance(enterNotifyEvents, str):
            self.enterNotifyEvents.text = enterNotifyEvents
        else:
            self.enterNotifyEvents.text = enterNotifyEvents.tag
        # exitNotifyEvents
        self.exitNotifyEvents = ET.SubElement(self.hkobject, 'hkparam')
        self.exitNotifyEvents.set("name", "exitNotifyEvents")
        if isinstance(exitNotifyEvents, str):
            self.exitNotifyEvents.text = exitNotifyEvents
        else:
            self.exitNotifyEvents.text = exitNotifyEvents.tag
            # transitions
        self.transitions = ET.SubElement(self.hkobject, 'hkparam')
        self.transitions.set("name", "transitions")
        self.transitions.text = transitions.tag
        # generator
        self.generator = ET.SubElement(self.hkobject, 'hkparam')
        self.generator.set("name", "generator")
        self.generator.text = generator.tag
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = name
        self.stateName = name
        # stateID
        self.stateID = ET.SubElement(self.hkobject, 'hkparam')
        self.stateID.set("name", "stateId")
        self.stateID.text = str(state_ID)
        self.stateIdx = state_ID
        # probability
        self.probability = ET.SubElement(self.hkobject, 'hkparam')
        self.probability.set("name", "probability")
        self.probability.text = "{:.06f}".format(1)
        # enable
        self.enable = ET.SubElement(self.hkobject, 'hkparam')
        self.enable.set("name", "enable")
        self.enable.text = "true"

    def getOrCreateClipTriggerArray(self, BehaviorFileObj):
        if self.hkbClipTriggerArray is None:
            self.hkbClipTriggerArray = hkbClipTriggerArray(BehaviorFileObj)
        return self.hkbClipTriggerArray


class hkbStateMachineEventPropertyArray:
    tag = "MISSING"
    hkobject = None
    num_elements = 0
    eventsParam = None

    def __init__(self, BehaviorFileObj, events=[]):
        assert isinstance(events, (list, str))
        print(events)
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbStateMachineEventPropertyArray')
        self.hkobject.set('signature', "0xb07b4388")

        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))

        # add base hkparam containing the events
        self.eventsParam = ET.SubElement(self.hkobject, 'hkparam')
        self.eventsParam.set("name", "events")
        # Check how many events
        if isinstance(events, list):
            self.num_elements = len(events)
        else:
            self.num_elements = 1
            events = [events]

        self.eventsParam.set("numelements", str(self.num_elements))

        # Add them
        for idx in range(0, self.num_elements):
            # get or create the event name
            eventID = BehaviorFileObj.hkbBehaviorGraphStringData.getOrCreateEventID(BehaviorFileObj=BehaviorFileObj,
                                                                                    event_name=events[idx])
            # create event object
            event_object = ET.SubElement(self.eventsParam, 'hkobject')
            # create event id param in event object
            event_object_id = ET.SubElement(event_object, 'hkparam')
            event_object_id.set("name", "id")
            event_object_id.text = str(eventID)
            # create payload param in event object
            event_object_payload = ET.SubElement(event_object, 'hkparam')
            event_object_payload.set("name", "payload")
            event_object_payload.text = "null"


class hkbClipTriggerArray:
    # class that can trigger (send) events at a given time during a generator playing
    tag = "MISSING"
    hkobject = None
    triggersParam = None
    num_elements = 0

    def __init__(self, BehaviorFileObj):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbClipTriggerArray')
        self.hkobject.set('signature', "0x59c23a0f")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # the triggers container
        self.triggersParam = ET.SubElement(self.hkobject, 'hkparam')
        self.triggersParam.set("name", "triggers")
        self.triggersParam.set("numelements", str(self.num_elements))

    def add_trigger(self, localTime, EventID, relativeToEndOfClip=False):
        assert isinstance(localTime, (float, int))
        assert isinstance(EventID, int)
        triggersObj = ET.SubElement(self.triggersParam, 'hkobject')
        # localTime
        localTimeParam = ET.SubElement(triggersObj, 'hkparam')
        localTimeParam.set("name", "localTime")
        localTimeParam.text = "{:.06f}".format(float(localTime))
        # eventParam
        eventParam = ET.SubElement(triggersObj, 'hkparam')
        eventParam.set("name", "event")
        # eventObj
        eventObj = ET.SubElement(eventParam, 'hkobject')
        # event_index
        event_index = ET.SubElement(eventObj, 'hkparam')
        event_index.set("name", "id")
        event_index.text = str(EventID)
        # payload
        payload = ET.SubElement(eventObj, 'hkparam')
        payload.set("name", "payload")
        payload.text = "null"

        # relativeToEndOfClip
        relativeToEndOfClipObj = ET.SubElement(triggersObj, 'hkparam')
        relativeToEndOfClipObj.set("name", "relativeToEndOfClip")
        if relativeToEndOfClip:
            relativeToEndOfClipObj.text = "true"
        else:
            relativeToEndOfClipObj.text = "false"
        # acyclic
        acyclic = ET.SubElement(triggersObj, 'hkparam')
        acyclic.set("name", "acyclic")
        acyclic.text = "false"
        # isAnnotation
        isAnnotation = ET.SubElement(triggersObj, 'hkparam')
        isAnnotation.set("name", "isAnnotation")
        isAnnotation.text = "false"

        # update the numelements
        self.num_elements += 1
        self.triggersParam.set("numelements", str(self.num_elements))


class hkbStateMachine:
    tag = "MISSING"
    name = "MISSING"
    nStates = 0
    list_of_states = []

    def __init__(self, BehaviorFileObj, name="defaultNameBehavior", startStateIdIdx=0):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbStateMachine')
        self.hkobject.set('signature', "0x816c1dcb")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' cachedBindables SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' areBindablesCached SERIALIZE_IGNORED '))
        # userData
        self.userData = ET.SubElement(self.hkobject, 'hkparam')
        self.userData.set("name", "userData")
        self.userData.text = "0"
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = name
        # comments
        self.hkobject.append(ET.Comment(' id SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' cloneState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' padNode SERIALIZE_IGNORED '))
        # eventToSendWhenStateOrTransitionChanges, its object and params
        self.eventToSendWhenStateOrTransitionChanges = ET.SubElement(self.hkobject, 'hkparam')
        self.eventToSendWhenStateOrTransitionChanges.set("name", "eventToSendWhenStateOrTransitionChanges")
        self.eventToSendWhenStateOrTransitionChangesObject = ET.SubElement(self.eventToSendWhenStateOrTransitionChanges,
                                                                           'hkobject')
        # idparam
        self.id = ET.SubElement(self.eventToSendWhenStateOrTransitionChangesObject, 'hkparam')
        self.id.set("name", "id")
        self.id.text = "-1"
        # payloadparam
        self.payload = ET.SubElement(self.eventToSendWhenStateOrTransitionChangesObject, 'hkparam')
        self.payload.set("name", "payload")
        self.payload.text = "null"
        self.eventToSendWhenStateOrTransitionChangesObject.append(ET.Comment(' sender SERIALIZE_IGNORED '))
        # startStateChooser
        self.startStateChooser = ET.SubElement(self.hkobject, 'hkparam')
        self.startStateChooser.set("name", "startStateChooser")
        self.startStateChooser.text = "null"
        # startStateId
        self.startStateId = ET.SubElement(self.hkobject, 'hkparam')
        self.startStateId.set("name", "startStateId")
        self.startStateId.text = str(startStateIdIdx)
        # returnToPreviousStateEventId
        self.returnToPreviousStateEventId = ET.SubElement(self.hkobject, 'hkparam')
        self.returnToPreviousStateEventId.set("name", "returnToPreviousStateEventId")
        self.returnToPreviousStateEventId.text = "-1"
        # randomTransitionEventId
        self.randomTransitionEventId = ET.SubElement(self.hkobject, 'hkparam')
        self.randomTransitionEventId.set("name", "randomTransitionEventId")
        self.randomTransitionEventId.text = "-1"
        # transitionToNextHigherStateEventId
        self.transitionToNextHigherStateEventId = ET.SubElement(self.hkobject, 'hkparam')
        self.transitionToNextHigherStateEventId.set("name", "transitionToNextHigherStateEventId")
        self.transitionToNextHigherStateEventId.text = "-1"
        # transitionToNextLowerStateEventId
        self.transitionToNextLowerStateEventId = ET.SubElement(self.hkobject, 'hkparam')
        self.transitionToNextLowerStateEventId.set("name", "transitionToNextLowerStateEventId")
        self.transitionToNextLowerStateEventId.text = "-1"
        # syncVariableIndex
        self.syncVariableIndex = ET.SubElement(self.hkobject, 'hkparam')
        self.syncVariableIndex.set("name", "syncVariableIndex")
        self.syncVariableIndex.text = "-1"
        # comment
        self.hkobject.append(ET.Comment(' currentStateId SERIALIZE_IGNORED '))
        # wrapAroundStateId
        self.wrapAroundStateId = ET.SubElement(self.hkobject, 'hkparam')
        self.wrapAroundStateId.set("name", "wrapAroundStateId")
        self.wrapAroundStateId.text = "false"
        # maxSimultaneousTransitions
        self.maxSimultaneousTransitions = ET.SubElement(self.hkobject, 'hkparam')
        self.maxSimultaneousTransitions.set("name", "maxSimultaneousTransitions")
        self.maxSimultaneousTransitions.text = "32"
        # startStateMode
        self.startStateMode = ET.SubElement(self.hkobject, 'hkparam')
        self.startStateMode.set("name", "startStateMode")
        self.startStateMode.text = "START_STATE_MODE_DEFAULT"
        # selfTransitionMode
        self.selfTransitionMode = ET.SubElement(self.hkobject, 'hkparam')
        self.selfTransitionMode.set("name", "selfTransitionMode")
        self.selfTransitionMode.text = "SELF_TRANSITION_MODE_NO_TRANSITION"
        # comment
        self.hkobject.append(ET.Comment(' isActive SERIALIZE_IGNORED '))
        # states
        self.states = ET.SubElement(self.hkobject, 'hkparam')
        self.states.set("name", "states")
        self.states.set("numelements", str(self.nStates))
        # wildcardTransitions
        self.wildcardTransitions = ET.SubElement(self.hkobject, 'hkparam')
        self.wildcardTransitions.set("name", "wildcardTransitions")
        if BehaviorFileObj.wildcardtransitions is not None:
            self.wildcardTransitions.text = BehaviorFileObj.wildcardtransitions.tag
        else:
            self.wildcardTransitions.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' stateIdToIndexMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' activeTransitions SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' transitionFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' wildcardTransitionFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' delayedTransitions SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' timeInState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' lastLocalTime SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' previousStateId SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' nextStartStateIndexOverride SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' stateOrTransitionChanged SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' echoNextUpdate SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' sCurrentStateIndexAndEntered SERIALIZE_IGNORED '))

    def add_state(self, state):
        assert isinstance(state, hkbStateMachineStateInfo)
        # add to internal list of states and increase counter
        self.nStates += 1
        self.list_of_states.append(state.tag)
        # rebuild state string
        self.states.text = "\n\t\t\t\t" + " ".join([x for x in self.list_of_states]) + "\n\t\t\t"
        # update nElements
        self.states.set("numelements", str(self.nStates))

    def add_wildcardTransitions(self, wildcardtransition):
        assert isinstance(wildcardtransition, hkbStateMachineTransitionInfoArray)
        self.wildcardTransitions.text = wildcardtransition.tag


class hkbBehaviorGraph:
    tag = "MISSING"

    def __init__(self, BehaviorFileObj, name="defaultNameBehavior"):
        assert isinstance(BehaviorFileObj, object)
        assert BehaviorFileObj.__class__.__name__ == "BehaviorFile"
        # header
        self.hkobject = ET.SubElement(BehaviorFileObj.data, 'hkobject')
        self.tag = BehaviorFileObj._OCnext()
        self.hkobject.set('name', self.tag)
        self.hkobject.set('class', 'hkbBehaviorGraph')
        self.hkobject.set('signature', "0xb1218f86")
        # comments
        self.hkobject.append(ET.Comment(' memSizeAndFlags SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' referenceCount SERIALIZE_IGNORED '))
        # variableBindingSet
        self.variableBindingSet = ET.SubElement(self.hkobject, 'hkparam')
        self.variableBindingSet.set("name", "variableBindingSet")
        self.variableBindingSet.text = "null"
        # comments
        self.hkobject.append(ET.Comment(' cachedBindables SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' areBindablesCached SERIALIZE_IGNORED '))
        # userData
        self.userData = ET.SubElement(self.hkobject, 'hkparam')
        self.userData.set("name", "userData")
        self.userData.text = "0"
        # name
        self.name = ET.SubElement(self.hkobject, 'hkparam')
        self.name.set("name", "name")
        self.name.text = name + ".hkb"
        # comments
        self.hkobject.append(ET.Comment(' id SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' cloneState SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' padNode SERIALIZE_IGNORED '))
        # variableMode
        self.variableMode = ET.SubElement(self.hkobject, 'hkparam')
        self.variableMode.set("name", "variableMode")
        self.variableMode.text = "VARIABLE_MODE_DISCARD_WHEN_INACTIVE"
        self.hkobject.append(ET.Comment(' uniqueIdPool SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' idToStateMachineTemplateMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' mirroredExternalIdMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' pseudoRandomGenerator SERIALIZE_IGNORED '))
        # rootGenerator
        self.rootGenerator = ET.SubElement(self.hkobject, 'hkparam')
        self.rootGenerator.set("name", "rootGenerator")
        self.rootGenerator.text = BehaviorFileObj.hkbStateMachineObj.tag
        # data
        self.data = ET.SubElement(self.hkobject, 'hkparam')
        self.data.set("name", "data")
        self.data.text = BehaviorFileObj.hkbBehaviorGraphData.tag
        self.hkobject.append(ET.Comment(' rootGeneratorClone SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' activeNodes SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' activeNodeTemplateToIndexMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' activeNodesChildrenIndices SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' globalTransitionData SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' eventIdMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' attributeIdMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' variableIdMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' characterPropertyIdMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' variableValueSet SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' nodeTemplateToCloneMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' nodeCloneToTemplateMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' stateListenerTemplateToCloneMap SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' nodePartitionInfo SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' numIntermediateOutputs SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' jobs SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' allPartitionMemory SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' numStaticNodes SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' nextUniqueId SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' isActive SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' isLinked SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' updateActiveNodes SERIALIZE_IGNORED '))
        self.hkobject.append(ET.Comment(' stateOrTransitionChanged SERIALIZE_IGNORED '))

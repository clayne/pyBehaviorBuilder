
#############################################################################
##
## Copyright (C) 2013 Riverbank Computing Limited.
## Copyright (C) 2021 The Qt Company Ltd.
## Contact: http://www.qt.io/licensing/
##
## This file is modified from Qt for Python examples of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:BSD$
## You may use this file under the terms of the BSD license as follows:
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##   * Redistributions of source code must retain the above copyright
##     notice, this list of conditions and the following disclaimer.
##   * Redistributions in binary form must reproduce the above copyright
##     notice, this list of conditions and the following disclaimer in
##     the documentation and/or other materials provided with the
##     distribution.
##   * Neither the name of The Qt Company Ltd nor the names of its
##     contributors may be used to endorse or promote products derived
##     from this software without specific prior written permission.
##
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
## $QT_END_LICENSE$
##
#############################################################################

import math
import sys

from PySide6.QtCore import (QLineF, QPointF, QRect, QRectF, QSize, QSizeF, Qt,QEventLoop, QTimer,
                            Signal,QObject,QEvent)
from PySide6.QtGui import (QAction, QColor, QFont, QFontMetrics, QIcon, QIntValidator,
                           QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform, QCloseEvent)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QCheckBox,QDialogButtonBox,
                               QFontComboBox, QFileDialog, QGraphicsAnchorLayout,
                               QGraphicsItem, QGraphicsLineItem,
                               QGraphicsPolygonItem, QGraphicsTextItem,QGraphicsSimpleTextItem,
                               QGraphicsScene, QGraphicsView, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QSizePolicy, QToolBox, QToolButton,
                               QVBoxLayout, QPushButton,QWidget)

import diagramscene_rc

from BehaviorBuilder import BehaviorFile

#Global event receiver/emitter object
#Credits to stackoverflow user eyllanesc
#https://stackoverflow.com/questions/55553660/how-to-emit-custom-events-to-the-event-loop-in-pyqt
import functools

@functools.lru_cache()
class GlobalObject(QObject):
    def __init__(self):
        super().__init__()
        self._events = {}

    def addEventListener(self, name, func):
        if name not in self._events:
            self._events[name] = [func]
        else:
            self._events[name].append(func)

    def dispatchEvent(self, name):
        functions = self._events.get(name, [])
        for func in functions:
            QTimer.singleShot(0, func)


class StatePopup(QWidget):

    def __init__(self, parent, stateNameStr, stateAnimationStr, stateWildCardStr, stateIsStartState):
        super(StatePopup, self).__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAutoFillBackground(True)
        self.setStyleSheet('''
            StatePopup {
                background: rgba(64, 64, 64, 64);
            }
            QWidget#container {
                border: 2px solid darkGray;
                border-radius: 4px;
                background: rgb(64, 64, 64);
            }
            QWidget#container > QLabel {
                color: white;
            }
            QLabel#title {
                font-size: 20pt;
            }
            QPushButton#close {
                color: white;
                font-weight: bold;
                background: none;
                border: 1px solid gray;
            }
        ''')

        self.stateNameStr=stateNameStr
        self.stateAnimationStr=stateAnimationStr
        self.stateWildCardStr=stateWildCardStr

        fullLayout = QVBoxLayout(self)

        self.container = QWidget(
            autoFillBackground=True, objectName='container')
        fullLayout.addWidget(self.container, alignment=Qt.AlignCenter)
        self.container.setSizePolicy(
            QSizePolicy.Maximum, QSizePolicy.Maximum)

        buttonSize = self.fontMetrics().height()
        self.closeButton = QPushButton(
            '×', self.container, objectName='close')
        self.closeButton.setFixedSize(buttonSize*2, buttonSize*2)
        self.closeButton.clicked.connect(self.reject)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(
            buttonSize * 2, buttonSize, buttonSize * 2, buttonSize)

        title = QLabel(
            'Specify state Properties', 
            objectName='title', alignment=Qt.AlignCenter)
        layout.addWidget(title)

        #Name
        layout.addWidget(QLabel('State name'))
        self.stateNameEdit = QLineEdit()
        self.stateNameEdit.setText(self.stateNameStr)
        layout.addWidget(self.stateNameEdit)

        self.isStarting = QCheckBox("This state is the default/starting state", self)
        self.isStarting.setStyleSheet("color: white")
        layout.addWidget(self.isStarting)
        if stateIsStartState:
            self.isStarting.setChecked(True)
        else:
            self.isStarting.setChecked(False)

        #Animation
        layout.addWidget(QLabel('Animation'))
        self.animationNameEdit = QLineEdit()
        self.animationNameEdit.setText(self.stateAnimationStr)
        layout.addWidget(self.animationNameEdit)

        #Wildcard event
        layout.addWidget(QLabel('Wildcard event'))
        self.wildcardNameEdit = QLineEdit()
        self.wildcardNameEdit.setText("")
        layout.addWidget(self.wildcardNameEdit)

        self.gameBryoAnimation = QCheckBox("Gamebryo animation", self)
        self.gameBryoAnimation.setStyleSheet("color: white")
        layout.addWidget(self.gameBryoAnimation)

        self.isLooping = QCheckBox("Looping Animation", self)
        self.isLooping.setStyleSheet("color: white")
        layout.addWidget(self.isLooping)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        layout.addWidget(buttonBox)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        self.okButton = buttonBox.button(buttonBox.Ok)
        self.okButton.setEnabled(True)

        self.stateNameEdit.textChanged.connect(self.stateName)
        self.animationNameEdit.textChanged.connect(self.animationName)
        self.wildcardNameEdit.textChanged.connect(self.wildcardName)
        self.gameBryoAnimation.stateChanged.connect(self.isGamebryoAnimState)
        self.isLooping.stateChanged.connect(self.isLoopingState)
        self.isStarting.stateChanged.connect(self.isStartingState)

        self.setWindowTitle("State properties")

        self.loop = QEventLoop(self)


    def closeEvent(self, event):
        #Ignore the corner 'X'
        event.ignore()
        return

    def isGamebryoAnimState(self):
        if self.gameBryoAnimation.isChecked():
            self.animationNameEdit.setText("")
            self.animationNameEdit.setEnabled(False)
            return True
        else:
            self.animationNameEdit.setText("animations\\animationName.hkx")
            self.animationNameEdit.setEnabled(True)
            return False

    def isLoopingState(self):
        if self.isLooping.isChecked():
            return True
        else:
            return False

    def isStartingState(self):
        if self.isStarting.isChecked():
            return True
        else:
            return False

    def stateName(self):
        self.stateNameStr=self.stateNameEdit.text()
        return self.stateNameEdit.text()



    def wildcardName(self):
        self.stateWildCardStr=self.wildcardNameEdit.text()
        return self.wildcardNameEdit.text()

    def animationName(self):
        self.stateAnimationStr=self.animationNameEdit.text()
        return self.animationNameEdit.text()

    def accept(self):
        if self.stateName() and (self.animationName() or self.gameBryoAnimation.isChecked()):
            self.loop.exit(True)

    def reject(self):
        self.loop.exit(False)


    def close(self):
        #self.loop.quit()
        self.loop.exit(False)

    def exec(self):
        self.show()
        #self._raise()
        res = self.loop.exec()
        self.hide()
        return res


class StateConnectionPopup(QWidget):

    def __init__(self, parent, state1NameStr, state2NameStr, stateEventStr):
        super(StateConnectionPopup, self).__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAutoFillBackground(True)
        self.setStyleSheet('''
            StatePopup {
                background: rgba(64, 64, 64, 64);
            }
            QWidget#container {
                border: 2px solid darkGray;
                border-radius: 4px;
                background: rgb(64, 64, 64);
            }
            QWidget#container > QLabel {
                color: white;
            }
            QLabel#title {
                font-size: 20pt;
            }
            QPushButton#close {
                color: white;
                font-weight: bold;
                background: none;
                border: 1px solid gray;
            }
        ''')

        self.state1NameStr=state1NameStr
        self.state2NameStr=state2NameStr
        self.stateEventStr=stateEventStr

        fullLayout = QVBoxLayout(self)

        self.container = QWidget(
            autoFillBackground=True, objectName='container')
        fullLayout.addWidget(self.container, alignment=Qt.AlignCenter)
        self.container.setSizePolicy(
            QSizePolicy.Maximum, QSizePolicy.Maximum)

        buttonSize = self.fontMetrics().height()
        self.closeButton = QPushButton(
            '×', self.container, objectName='close')
        self.closeButton.setFixedSize(buttonSize, buttonSize)
        self.closeButton.clicked.connect(self.reject)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(
            buttonSize * 2, buttonSize, buttonSize * 2, buttonSize)

        title = QLabel(
            'Connect states:', 
            objectName='title', alignment=Qt.AlignCenter)
        layout.addWidget(title)

        #Name
        layout.addWidget(QLabel(self.state1NameStr+' to '+self.state2NameStr))


        #event
        layout.addWidget(QLabel('event'))
        self.stateEventEdit = QLineEdit()
        self.stateEventEdit.setText(self.stateEventStr)
        layout.addWidget(self.stateEventEdit)


        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        layout.addWidget(buttonBox)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        self.okButton = buttonBox.button(buttonBox.Ok)
        self.okButton.setEnabled(False)

        self.stateEventEdit.textChanged.connect(self.checkInput)

        self.setWindowTitle("State connector")

        self.loop = QEventLoop(self)

    def closeEvent(self, event):
        #Ignore the corner 'X'
        event.ignore()
        return

    def checkInput(self):
         self.eventName()
         self.okButton.setEnabled(bool(self.eventName()))

    def eventName(self):
        self.stateEventStr=self.stateEventEdit.text()
        return self.stateEventEdit.text()

    def accept(self):
        if self.eventName():
            self.loop.exit(True)

    def reject(self):
        self.loop.exit(False)

    def close(self):
        self.loop.quit()

    def exec(self):
        self.show()
        #self._raise()
        res = self.loop.exec()
        self.hide()
        return res


class Arrow(QGraphicsLineItem):

    stateEventStr="defaultEvent"

    def __init__(self, startItem, endItem, parent=None, scene=None):
        super().__init__(parent, scene)

        self._arrow_head = QPolygonF()

        self._my_start_item = startItem
        self._my_end_item = endItem
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self._my_color = Qt.black
        self.setPen(QPen(self._my_color, 2, Qt.SolidLine,
                Qt.RoundCap, Qt.RoundJoin))

    def set_color(self, color):
        self._my_color = color

    def start_item(self):
        return self._my_start_item

    def end_item(self):
        return self._my_end_item

    def boundingRect(self):
        extra = (self.pen().width() + 20) / 2.0
        p1 = self.line().p1()
        p2 = self.line().p2()
        rect = QRectF(p1, QSizeF(p2.x() - p1.x(), p2.y() - p1.y()))
        return rect.normalized().adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path = super(Arrow, self).shape()
        path.addPolygon(self._arrow_head)
        return path

    def update_position(self):
        start = self.mapFromItem(self._my_start_item, 0, 0)
        end = self.mapFromItem(self._my_end_item, 0, 0)
        self.setLine(QLineF(start, end))


    def paint(self, painter, option, widget=None):
        if (self._my_start_item.collidesWithItem(self._my_end_item)):
            return

        my_start_item = self._my_start_item
        my_end_item = self._my_end_item
        my_color = self._my_color
        my_pen = self.pen()
        my_pen.setColor(self._my_color)
        arrow_size = 20.0
        painter.setPen(my_pen)
        painter.setBrush(self._my_color)

        center_line = QLineF(my_start_item.pos(), my_end_item.pos())
        end_polygon = my_end_item.polygon()
        p1 = end_polygon.at(0) + my_end_item.pos()

        intersect_point = QPointF()
        for i in end_polygon:
            p2 = i + my_end_item.pos()
            poly_line = QLineF(p1, p2)
            intersectType, intersect_point = poly_line.intersects(center_line)
            if intersectType == QLineF.BoundedIntersection:
                break
            p1 = p2

        self.setLine(QLineF(intersect_point, my_start_item.pos()))
        line = self.line()

        angle = math.acos(line.dx() / line.length())
        if line.dy() >= 0:
            angle = (math.pi * 2.0) - angle

        arrow_head1 = QPointF(math.sin(angle + math.pi / 3.0) * arrow_size,
                              math.cos(angle + math.pi / 3) * arrow_size)
        arrow_p1 = line.p1() + arrow_head1
        arrow_head2 = QPointF(math.sin(angle + math.pi - math.pi / 3.0) * arrow_size,
                              math.cos(angle + math.pi - math.pi / 3.0) * arrow_size)
        arrow_p2 = line.p1() + arrow_head2

        self._arrow_head.clear()
        for point in [line.p1(), arrow_p1, arrow_p2]:
            self._arrow_head.append(point)

        painter.drawLine(line)
        painter.drawPolygon(self._arrow_head)
        if self.isSelected():
            painter.setPen(QPen(my_color, 1, Qt.DashLine))
            my_line = QLineF(line)
            my_line.translate(0, 4.0)
            painter.drawLine(my_line)
            my_line.translate(0, -8.0)
            painter.drawLine(my_line)

    def mouseDoubleClickEvent(self, event):
        stateData = StateConnectionPopup(self, self._my_start_item.getStateName(),  self._my_end_item.getStateName(), self.stateEventStr)
        stateData.setWindowFlag(Qt.WindowCloseButtonHint, False)
        if stateData.exec():
            self.stateEventStr=stateData.stateEventStr



class DiagramTextItem(QGraphicsTextItem):
    lost_focus = Signal(QGraphicsTextItem)

    selected_change = Signal(QGraphicsItem)

    def __init__(self, parent=None, scene=None):
        super().__init__(parent, scene)

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.selected_change.emit(self)
        return value

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.lost_focus.emit(self)
        super(DiagramTextItem, self).focusOutEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.textInteractionFlags() == Qt.NoTextInteraction:
            self.setTextInteractionFlags(Qt.TextEditorInteraction)
        super(DiagramTextItem, self).mouseDoubleClickEvent(event)


class StateItem(QGraphicsPolygonItem):
    Step, Conditional, StartEnd, Io = range(4)

    stateNameStr=""
    stateAnimationStr="animations\\animationName.hkx"
    stateWildCardStr=""
    stateGamebryoAnim=False
    stateIsLooping=False
    stateIsStartState=False

    def __init__(self, diagram_type, contextMenu, parent=None, scene=None):
        super().__init__(parent, scene)

        self.arrows = []

        self.diagram_type = diagram_type
        self._my_context_menu = contextMenu

        path = QPainterPath()
        if self.diagram_type == self.StartEnd:
            path.moveTo(200, 50)
            path.arcTo(150, 0, 50, 50, 0, 90)
            path.arcTo(50, 0, 50, 50, 90, 90)
            path.arcTo(50, 50, 50, 50, 180, 90)
            path.arcTo(150, 50, 50, 50, 270, 90)
            path.lineTo(200, 25)
            self._my_polygon = path.toFillPolygon()
        elif self.diagram_type == self.Conditional:
            self._my_polygon = QPolygonF([
                    QPointF(-100, 0), QPointF(0, 100),
                    QPointF(100, 0), QPointF(0, -100),
                    QPointF(-100, 0)])
        elif self.diagram_type == self.Step:
            self._my_polygon = QPolygonF([
                    QPointF(-100, -100), QPointF(100, -100),
                    QPointF(100, 100), QPointF(-100, 100),
                    QPointF(-100, -100)])
        else:
            self._my_polygon = QPolygonF([
                    QPointF(-120, -80), QPointF(-70, 80),
                    QPointF(120, 80), QPointF(70, -80),
                    QPointF(-120, -80)])

        self.setPolygon(self._my_polygon)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self._my_label_font = QFont()
        self._my_label_font.setWeight(QFont.Bold)
        self._my_label_font.setPointSize(18)
        self._my_label=QGraphicsSimpleTextItem(self.stateNameStr, parent=self)
        self._my_label.setFont(self._my_label_font)
        self.fontMetricsObj = QFontMetrics(self._my_label_font)
        width = self.fontMetricsObj.horizontalAdvance(self.stateNameStr)
        height = self.fontMetricsObj.height()
        self._my_label.setPos( -width/2, -height/2)

    def remove_arrow(self, arrow):
        try:
            self.arrows.remove(arrow)
        except ValueError:
            pass

    def remove_arrows(self):
        for arrow in self.arrows[:]:
            arrow.start_item().remove_arrow(arrow)
            arrow.end_item().remove_arrow(arrow)
            self.scene().removeItem(arrow)

    def add_arrow(self, arrow):
        self.arrows.append(arrow)

    def image(self):
        pixmap = QPixmap(250, 250)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.black, 8))
        painter.translate(125, 125)
        painter.drawPolyline(self._my_polygon)
        return pixmap

    def textDraw(self):
        if self.stateNameStr != "":
            self._my_label.setText(self.stateNameStr)
            

    def contextMenuEvent(self, event):
        self.scene().clearSelection()
        self.setSelected(True)
        self._my_context_menu.exec(event.screenPos())

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            for arrow in self.arrows:
                arrow.updatePosition()

        if self.stateNameStr != "" and self.stateNameStr != self._my_label.text():
            self.textDraw()
            width = self.fontMetricsObj.horizontalAdvance(self.stateNameStr)
            height = self.fontMetricsObj.height()
            self._my_label.setPos( -width/2, -height/2)

        return value


    def getStateName(self):
        return self.stateNameStr

    def dispatchCheckUniques(self):
        GlobalObject().dispatchEvent("checkUniqueSettings")

    def mouseDoubleClickEvent(self, event):
        stateData = StatePopup(self, self.stateNameStr,  self.stateAnimationStr, self.stateWildCardStr, self.stateIsStartState)
        stateData.setWindowFlag(Qt.WindowCloseButtonHint, False)
        if stateData.exec():
            self.stateNameStr=stateData.stateNameStr
            self.stateAnimationStr=stateData.stateAnimationStr
            self.stateWildCardStr=stateData.stateWildCardStr
            self.stateGamebryoAnim=stateData.isGamebryoAnimState()
            self.stateIsLooping=stateData.isLoopingState()
            self.stateIsStartState = stateData.isStartingState()
            if self.stateIsStartState:
                #ToDo, parse all other states and make sure only one start state.
                #has to be in diagramscene
                self.dispatchCheckUniques()


class DiagramScene(QGraphicsScene):
    InsertItem, InsertLine, InsertText, MoveItem = range(4)

    item_inserted = Signal(StateItem)

    text_inserted = Signal(QGraphicsTextItem)

    item_selected = Signal(QGraphicsItem)

    def __init__(self, itemMenu, parent=None):
        super().__init__(parent)

        self._my_item_menu = itemMenu
        self._my_mode = self.MoveItem
        self._my_item_type = StateItem.Step
        self.line = None
        self._text_item = None
        self._my_item_color = Qt.white
        self._my_text_color = Qt.black
        self._my_line_color = Qt.black
        self._my_font = QFont()

        #Listen for unique-check event
        GlobalObject().addEventListener("checkUniqueSettings", self.checkUniqueWidgetOptions)


    def checkUniqueWidgetOptions(self):
        print("Checking unique settings")
        stateList=[] #name, stateIsStartState, item
        for item in self.items():
            if isinstance(item, StateItem):
                stateList.append([item.stateNameStr, item.stateIsStartState, item])
        
        if sum([stateItem[1] for stateItem in stateList]) > 1:
            #Too many start states
            for stateItem in stateList:
                stateItem[2].stateIsStartState=False
            reportStr="Too many states are selected as starting/default state, disabling all. Re-select starting state for only one."
            print(reportStr)

    def set_line_color(self, color):
        self._my_line_color = color
        if self.is_item_change(Arrow):
            item = self.selectedItems()[0]
            item.set_color(self._my_line_color)
            self.update()

    def set_text_color(self, color):
        self._my_text_color = color
        if self.is_item_change(DiagramTextItem):
            item = self.selectedItems()[0]
            item.setDefaultTextColor(self._my_text_color)

    def set_item_color(self, color):
        self._my_item_color = color
        if self.is_item_change(StateItem):
            item = self.selectedItems()[0]
            item.setBrush(self._my_item_color)

    def set_font(self, font):
        self._my_font = font
        if self.is_item_change(DiagramTextItem):
            item = self.selectedItems()[0]
            item.setFont(self._my_font)

    def set_mode(self, mode):
        self._my_mode = mode

    def set_item_type(self, type):
        self._my_item_type = type

    def editor_lost_focus(self, item):
        cursor = item.textCursor()
        cursor.clearSelection()
        item.setTextCursor(cursor)

        if not item.toPlainText():
            self.removeItem(item)
            item.deleteLater()

    def mousePressEvent(self, mouseEvent):
        if (mouseEvent.button() != Qt.LeftButton):
            return

        if self._my_mode == self.InsertItem:
            item = StateItem(self._my_item_type, self._my_item_menu)
            item.setBrush(self._my_item_color)
            self.addItem(item)
            item.setPos(mouseEvent.scenePos())
            self.item_inserted.emit(item)
        elif self._my_mode == self.InsertLine:
            self.line = QGraphicsLineItem(QLineF(mouseEvent.scenePos(),
                                        mouseEvent.scenePos()))
            self.line.setPen(QPen(self._my_line_color, 2))
            self.addItem(self.line)
        elif self._my_mode == self.InsertText:
            text_item = DiagramTextItem()
            text_item.setFont(self._my_font)
            text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            text_item.setZValue(1000.0)
            text_item.lost_focus.connect(self.editor_lost_focus)
            text_item.selected_change.connect(self.item_selected)
            self.addItem(text_item)
            text_item.setDefaultTextColor(self._my_text_color)
            text_item.setPos(mouseEvent.scenePos())
            self.text_inserted.emit(text_item)

        super(DiagramScene, self).mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        if self._my_mode == self.InsertLine and self.line:
            new_line = QLineF(self.line.line().p1(), mouseEvent.scenePos())
            self.line.setLine(new_line)
        elif self._my_mode == self.MoveItem:
            super(DiagramScene, self).mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        if self.line and self._my_mode == self.InsertLine:
            start_items = self.items(self.line.line().p1())
            if len(start_items) and start_items[0] == self.line:
                start_items.pop(0)
            end_items = self.items(self.line.line().p2())
            if len(end_items) and end_items[0] == self.line:
                end_items.pop(0)

            self.removeItem(self.line)
            self.line = None

            if (len(start_items) and len(end_items) and
                    isinstance(start_items[0], StateItem) and
                    isinstance(end_items[0], StateItem) and
                    start_items[0] != end_items[0]):
                start_item = start_items[0]
                end_item = end_items[0]
                arrow = Arrow(start_item, end_item)
                arrow.set_color(self._my_line_color)
                start_item.add_arrow(arrow)
                end_item.add_arrow(arrow)
                arrow.setZValue(-1000.0)
                self.addItem(arrow)
                arrow.update_position()

        self.line = None
        super(DiagramScene, self).mouseReleaseEvent(mouseEvent)


    def is_item_change(self, type):
        for item in self.selectedItems():
            if isinstance(item, type):
                return True
        return False


class MainWindow(QMainWindow):
    insert_text_button = 10

    def __init__(self):
        super().__init__()

        self.create_actions()
        self.create_menus()
        self.create_tool_box()

        self.scene = DiagramScene(self._item_menu)
        self.scene.setSceneRect(QRectF(0, 0, 5000, 5000))
        self.scene.item_inserted.connect(self.item_inserted)
        self.scene.text_inserted.connect(self.text_inserted)
        self.scene.item_selected.connect(self.item_selected)

        self.create_toolbars()

        layout = QHBoxLayout()
        layout.addWidget(self._tool_box)
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view)

        self.widget = QWidget()
        self.widget.setLayout(layout)

        self.setCentralWidget(self.widget)
        self.setWindowTitle("Skyrim static Behavior .xml creator")
        self.view.installEventFilter(self)

    def background_button_group_clicked(self, button):
        buttons = self._background_button_group.buttons()
        for myButton in buttons:
            if myButton != button:
                button.setChecked(False)

        text = button.text()
        if text == "Blue Grid":
            self.scene.setBackgroundBrush(QBrush(QPixmap(':/images/background1.png')))
        elif text == "White Grid":
            self.scene.setBackgroundBrush(QBrush(QPixmap(':/images/background2.png')))
        elif text == "Gray Grid":
            self.scene.setBackgroundBrush(QBrush(QPixmap(':/images/background3.png')))
        else:
            self.scene.setBackgroundBrush(QBrush(QPixmap(':/images/background4.png')))

        self.scene.update()
        self.view.update()

    def button_group_clicked(self, idx):
        buttons = self._button_group.buttons()
        for button in buttons:
            if self._button_group.button(idx) != button:
                button.setChecked(False)

        if idx == self.insert_text_button:
            self.scene.set_mode(DiagramScene.InsertText)
        else:
            self.scene.set_item_type(idx)
            self.scene.set_mode(DiagramScene.InsertItem)

    def delete_item(self):
        for item in self.scene.selectedItems():
            if isinstance(item, StateItem):
                item.remove_arrows()
            self.scene.removeItem(item)

    def pointer_group_clicked(self, i):
        self.scene.set_mode(self._pointer_type_group.checkedId())

    def bring_to_front(self):
        if not self.scene.selectedItems():
            return

        selected_item = self.scene.selectedItems()[0]
        overlap_items = selected_item.collidingItems()

        z_value = 0
        for item in overlap_items:
            if (item.zValue() >= z_value and isinstance(item, StateItem)):
                z_value = item.zValue() + 0.1
        selected_item.setZValue(z_value)

    def send_to_back(self):
        if not self.scene.selectedItems():
            return

        selected_item = self.scene.selectedItems()[0]
        overlap_items = selected_item.collidingItems()

        z_value = 0
        for item in overlap_items:
            if (item.zValue() <= z_value and isinstance(item, StateItem)):
                z_value = item.zValue() - 0.1
        selected_item.setZValue(z_value)

    def item_inserted(self, item):
        self._pointer_type_group.button(DiagramScene.MoveItem).setChecked(True)
        self.scene.set_mode(self._pointer_type_group.checkedId())
        self._button_group.button(item.diagram_type).setChecked(False)

    def text_inserted(self, item):
        self._button_group.button(self.insert_text_button).setChecked(False)
        self.scene.set_mode(self._pointer_type_group.checkedId())


    def scene_scale_changed(self, scale):
        new_scale = int(scale[:-1]) / 100.0
        old_matrix = self.view.transform()
        self.view.resetTransform()
        self.view.translate(old_matrix.dx(), old_matrix.dy())
        self.view.scale(new_scale, new_scale)


    def line_button_triggered(self):
        self.scene.set_line_color(QColor(self._line_action.data()))

    def handle_font_change(self):
        font = self._font_combo.currentFont()
        font.setPointSize(int(self._font_size_combo.currentText()))
        if self._bold_action.isChecked():
            font.setWeight(QFont.Bold)
        else:
            font.setWeight(QFont.Normal)
        font.setItalic(self._italic_action.isChecked())
        font.setUnderline(self._underline_action.isChecked())

        self.scene.set_font(font)

    def item_selected(self, item):
        font = item.font()
        color = item.defaultTextColor()
        self._font_combo.setCurrentFont(font)
        self._font_size_combo.setEditText(str(font.pointSize()))
        self._bold_action.setChecked(font.weight() == QFont.Bold)
        self._italic_action.setChecked(font.italic())
        self._underline_action.setChecked(font.underline())

    def about(self):
        QMessageBox.about(self, "About BehaviorBuilder_GUI",
                "<b>BehaviorBuilder_GUI</b> is a pySide6 GUI wrapper for BehaviorBuilder to create and export skyrim .xml behaviors.")

    def create_tool_box(self):
        self._button_group = QButtonGroup()
        self._button_group.setExclusive(False)
        self._button_group.idClicked.connect(self.button_group_clicked)

        layout = QGridLayout()
        layout.addWidget(self.create_cell_widget("State", StateItem.Conditional),
                0, 0)


        layout.setRowStretch(3, 10)
        layout.setColumnStretch(2, 10)

        item_widget = QWidget()
        item_widget.setLayout(layout)

        self._tool_box = QToolBox()
        self._tool_box.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Ignored))
        self._tool_box.setMinimumWidth(item_widget.sizeHint().width())
        self._tool_box.addItem(item_widget, "State widgets")


    def export_file(self):
        fileName, selectedFilter = QFileDialog.getSaveFileName(self, "Save File","","Havok .xml file (*.xml)")
        #Loop over items and extract states, connections and wildcards
        stateList=[]
        connectionList=[]
        wildcardList=[]

        for w in self.scene.items():
            
            if isinstance(w, StateItem):
                name=w.stateNameStr
                if not w.stateGamebryoAnim:
                    animation_path=w.stateAnimationStr
                    gamebryoanim=False
                else:
                    animation="placeholder"
                    gamebryoanim=True
                looping=False
                stateList.append( (name,animation_path,looping,gamebryoanim) )
                if w.stateWildCardStr!="":
                    wildcardList.append( (name, w.stateWildCardStr) )
            elif isinstance(w, Arrow):
                state1=w._my_start_item.getStateName()
                state2=w._my_end_item.getStateName()
                event=w.stateEventStr
                connectionList.append( (state1,state2,event) )

        #Create behavior file object
        bf = BehaviorFile()

        for name,animation_path,looping,gamebryoanim in stateList:
            bf.add_state(name=name,animation_path=animation_path,looping=looping,gamebryoanim=gamebryoanim)
        for state1,state2, event in connectionList:
            bf.connect_states(state1=state1, state2=state2, event=event)
        if wildcardList:
            for stateStr, event in wildcardList:
                bf.add_wildcard(stateStr=stateStr, event=event)

        #Todo set starting state
        #-----------------------
        #Might need tweaks in the Behavior factory


        #Export
        bf.export(fileName)


    def create_actions(self):
        self._to_front_action = QAction(
                QIcon(':/images/bringtofront.png'), "Bring to &Front",
                self, shortcut="Ctrl+F", statusTip="Bring item to front",
                triggered=self.bring_to_front)

        self._send_back_action = QAction(
                QIcon(':/images/sendtoback.png'), "Send to &Back", self,
                shortcut="Ctrl+B", statusTip="Send item to back",
                triggered=self.send_to_back)

        self._delete_action = QAction(QIcon(':/images/delete.png'),
                "&Delete", self, shortcut="Delete",
                statusTip="Delete item from diagram",
                triggered=self.delete_item)

        self._exit_action = QAction("E&xit", self, shortcut="Ctrl+X",
                statusTip="Quit Scenediagram example", triggered=self.close)

        self._export_action = QAction(QIcon(''),
                "&Export", self, shortcut="Ctrl+E",
                statusTip="Export state machine to .xml",
                triggered=self.export_file)



        self._about_action = QAction("A&bout", self, shortcut="Ctrl+B",
                triggered=self.about)

    def create_menus(self):
        self._file_menu = self.menuBar().addMenu("&File")
        self._file_menu.addAction(self._export_action)
        self._file_menu.addAction(self._exit_action)

        self._item_menu = self.menuBar().addMenu("&Item")
        self._item_menu.addAction(self._delete_action)
        self._item_menu.addSeparator()
        self._item_menu.addAction(self._to_front_action)
        self._item_menu.addAction(self._send_back_action)

        self._about_menu = self.menuBar().addMenu("&Help")
        self._about_menu.addAction(self._about_action)

    def create_toolbars(self):
        self._edit_tool_bar = self.addToolBar("Edit")
        self._edit_tool_bar.addAction(self._delete_action)
        self._edit_tool_bar.addAction(self._to_front_action)
        self._edit_tool_bar.addAction(self._send_back_action)

        pointer_button = QToolButton()
        pointer_button.setCheckable(True)
        pointer_button.setChecked(True)
        pointer_button.setIcon(QIcon(':/images/pointer.png'))
        line_pointer_button = QToolButton()
        line_pointer_button.setCheckable(True)
        line_pointer_button.setIcon(QIcon(':/images/linepointer.png'))

        self._pointer_type_group = QButtonGroup()
        self._pointer_type_group.addButton(pointer_button, DiagramScene.MoveItem)
        self._pointer_type_group.addButton(line_pointer_button,
                DiagramScene.InsertLine)
        self._pointer_type_group.idClicked.connect(self.pointer_group_clicked)

        self._scene_scale_combo = QComboBox()
        self._scene_scale_combo.addItems(["50%", "75%", "100%", "125%", "150%"])
        self._scene_scale_combo.setCurrentIndex(2)
        self._scene_scale_combo.currentTextChanged.connect(self.scene_scale_changed)

        self._pointer_toolbar = self.addToolBar("Pointer type")
        self._pointer_toolbar.addWidget(pointer_button)
        self._pointer_toolbar.addWidget(line_pointer_button)
        self._pointer_toolbar.addWidget(self._scene_scale_combo)

    def create_background_cell_widget(self, text, image):
        button = QToolButton()
        button.setText(text)
        button.setIcon(QIcon(image))
        button.setIconSize(QSize(50, 50))
        button.setCheckable(True)
        self._background_button_group.addButton(button)

        layout = QGridLayout()
        layout.addWidget(button, 0, 0, Qt.AlignHCenter)
        layout.addWidget(QLabel(text), 1, 0, Qt.AlignCenter)

        widget = QWidget()
        widget.setLayout(layout)

        return widget

    def create_cell_widget(self, text, diagram_type):
        item = StateItem(diagram_type, self._item_menu)
        icon = QIcon(item.image())

        button = QToolButton()
        button.setIcon(icon)
        button.setIconSize(QSize(50, 50))
        button.setCheckable(True)
        self._button_group.addButton(button, diagram_type)

        layout = QGridLayout()
        layout.addWidget(button, 0, 0, Qt.AlignHCenter)
        layout.addWidget(QLabel(text), 1, 0, Qt.AlignCenter)

        widget = QWidget()
        widget.setLayout(layout)

        return widget



if __name__ == '__main__':
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.setGeometry(100, 100, 800, 500)
    main_window.show()

    sys.exit(app.exec())

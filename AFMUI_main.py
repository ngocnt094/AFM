from datetime import datetime
import logging
import os
import sys
from ui.DevicePortWidget import DevicePortWidget
from ui.ConnectionWidget import ConnectionWidget

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

from comm.HubClient import HubClient
from data.HubMonitor import HubMonitor
from data.HubStatus import HubStatus
from ui.DeviceStatusWidget import DeviceStatusWidget
from utils.setup import setup_logging
from data.ProgramHubLogger import ProgramHubLogger

import matplotlib        
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg  import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from numpy import random
import csv
import threading
import pandas
import numpy as np
import time
import multiprocessing as mp

logger = logging.getLogger("AFM App")

### real time when starting the program
dt0 = datetime.now()
#print(dt0)
dt0_str = dt0.strftime('%Y-%m-%d %H:%M:%S')
dt_now = datetime.strptime(dt0_str, '%Y-%m-%d %H:%M:%S')
dt_str_test = "2023-04-27 19:03:55"
dt_now_test = datetime.strptime(dt_str_test, '%Y-%m-%d %H:%M:%S')
print(dt_now)
log_filename = os.path.dirname(__file__) + "\logs\AFM_log.log"
data_file = os.path.dirname(__file__) + "\logs\AFM_data"
setup_logging(log_filename)



import os, os.path
config_file = os.path.join(os.path.abspath(os.getcwd()), 'lego_hub.yaml')
print("appdirs name:", os.path.abspath(os.getcwd()))
print("config_file", config_file)

def list_programs(info):
    storage = info['storage']
    slots = info['slots']
    print("%4s %-40s %6s %-20s %-12s %-10s" % ("Slot", "Decoded Name", "Size",  "Last Modified", "Project_id", "Type"))
    for i in range(20):
        if str(i) in slots:
            sl = slots[str(i)]
            modified = datetime.utcfromtimestamp(sl['modified']/1000).strftime('%Y-%m-%d %H:%M:%S')
            try:
                decoded_name = base64.b64decode(sl['name']).decode('utf-8')
            except:
                decoded_name = sl['name']
            try:
                project = sl['project_id']
            except:
                project = " "
            try:
                type = sl['type']
            except:
                type = " "
            print("%4s %-40s %5db %-20s %-12s %-10s" % (i, decoded_name, sl['size'], modified, project, type))
    print(("Storage free %s%s of total %s%s" % (storage['free'], storage['unit'], storage['total'], storage['unit'])))

def open_log(logFile: str, dataFile: str, dt):
    list_rows = []
    headers = ['x', 'y', 'I_low', 'I_up']
    with open(logFile) as fo:
        for rec in fo:
            
            idx =  rec.rfind("Program output: {")
            
            
            if not idx == -1 :
                rec_time = rec
                datetime_str = rec_time[0:19]
                datetime_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                
                if datetime_obj >= dt:
                    data = rec[idx+16:]
                    data_dict = eval(data)
                    #print(data)
                    
                    rows = [data_dict['x'] , data_dict['y'], data_dict['light_low'], data_dict['light_up']]

                    list_rows.append(rows)
    
    with open(dataFile, 'w') as f:
        write = csv.writer(f)
        write.writerow(headers)
        write.writerows(list_rows)
        

def read_data(dataFile):
    #print(data_File)
    df = pandas.read_csv(dataFile, sep=",", header= 0)
    data_array = np.array(df)
    X = data_array[:,0]
    Y = data_array[:, 1]
    light_down =  data_array[:, 2]
    light_up =  data_array[:, 3]
    
    
    interval_X =[ X[i+1]-X[i] for i in range(len(X) -1)]
    #print("interval_X", interval_X)
    #print("interval_X: ", interval_X)
    
    
    ## Convert X data
    
    g_start_list = [0]
    g_end_list = []
    sum_interval_list = []       
    g_start = 0   
    interval_after_list = [0]
    
    for g in range(len(interval_X)-1):   
        #sum_interval_list = []       
        #g_start = 0   
        #interval_after_list = [0]    
        #g_end_list = []
        #g_start_list = []
        if ((interval_X[g]* interval_X[g+1])<=0) & (interval_X[g+1] != 0):
            g_end = g-1
            #print(g_end)
            g_end_list.append(g_end)
            
            
            
            
            
            sum_interval = sum(interval_X[g_start:g_end+1])
            #print("sum interval: ", sum_interval)
            sum_interval_list.append(sum_interval)
            
            for h in range(g_start, g_end+1):
                if sum_interval >0:#interval_X[h] >= 0 :
                    interval_after = sum(interval_X[g_start:h+1])/sum_interval
                    #print("h is ", h, " and its relevant interval is : ", interval_after, "check its relevant sum: ", sum(interval_X[g_start:h+1]))
            
                if sum_interval <0: #interval_X[h] <=0:
                    interval_after = sum(interval_X[h+1:g_end+1])/sum_interval if sum(interval_X[h+1:g_end+1]) != 0 else float(0)
                    #print("h is ", h, " and its relevant interval is : ", interval_after, "check its relevant sum: ", sum(interval_X[g_start:h+1]), "or ", sum(interval_X[h+1:g_end+1]))
                #print("interval_after: ", interval_after)
                interval_after_list.append(round(interval_after, 3))
    
            g_start = g  
            g_start_list.append(g_start)
    #print("interval after list: ", interval_after_list)
    #print("sum_interval_list: ", sum_interval_list)
    
    
    #print("g start list : ", g_start_list)
        
    #print("g end list : ", g_end_list)
        
        #print("sum_interval list: ", sum_interval_list)
    ## COnvert Y data 
    Y_convert_list = [0]*len(interval_after_list)
    k_min = 0
    k_min_list = [0]
    for k in range(len(X) -2):
        #if ((X[k+1]-X[k]) * (X[k+2]- X[k+1])) < 0:
        if ((interval_X[k]* interval_X[k+1])<=0) & (interval_X[k+1] != 0):
            k_max = k -1
            #print("k max: ", k_max)
            
            #averaging_y = sum(Y[k_min:k_max +1])/ (k_max - k_min +1)
            #Y_averaging_list.append(averaging_y)
            for t in range(k_min, k_max+1):
                #Y[t] = averaging_y
                Y_convert_list[t] = k_min_list.index(k_min)
            k_min = k
            k_min_list.append(k_min)
    #print("k min list ", k_min_list)        
    z = np.round(np.add(10* light_up[0:len(interval_after_list)], light_down[0:len(interval_after_list)])/2, 2)
    z_max = np.max(z)

    #print(z, "max of z is ", z_max)
    z_scaled = np.round(4*z/z_max,3)
    Z_reshape = [z_scaled]*len(interval_after_list)
    n = int(len(Y_convert_list)/len(k_min_list))
    m = len(k_min_list)
    Y_to_plot = np.array(Y_convert_list)[0:n*m].reshape(n,m )
    Y_convert_array  =  np.array(Y_convert_list)
    #Y_convert_array = 65*Y_convert_array/(np.max(Y_convert_array))
    X_scaled = np.array(interval_after_list)*80#np.max(Y_to_plot)
    X_to_plot = X_scaled[0:n*m].reshape(n,m )
    
    Z_to_plot = z_scaled[0:n*m].reshape(n,m )
    
    #return X_to_plot, Y_to_plot, Z_to_plot
    return X_scaled, Y_convert_array, z_scaled

# main window UI from here
class MainWindow(QWidget):
    def __init__(self, hub_client: HubClient, hub_monitor : HubMonitor) -> None:
        super().__init__()
        self.setWindowTitle("AFM LEGO")
        self._client = hub_client
        self._monitor = hub_monitor
        
        self.setpoint_button = QPushButton("SET POINT")
        self.run_button = QPushButton("RUN")
        self.run_button.clicked.connect(self.run_program)
        self.stop_button = QPushButton("STOP")
        self.stop_button.clicked.connect(self.stop_program)
        
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.setpoint_button)                                                                      
        self.button_layout.addWidget(self.run_button)
        self.button_layout.addWidget(self.stop_button)
        #self.setLayout(button_layout)
        
        #Radio button automatically exclusive
        self.resolution = QGroupBox("Select Resolution")
        self.reso_20 = QRadioButton("20 x 20")
        self.reso_30 = QRadioButton("30 x 30")
        self.reso_40 = QRadioButton("40 x 40")
        self.reso_50 = QRadioButton("50 x 50")
        self.reso_60 = QRadioButton("60 x 60")
        self.reso_70 = QRadioButton("70 x 70")
        
        self.resolution_layout = QHBoxLayout()
        self.resolution_V_layout1 = QVBoxLayout()
        self.resolution_V_layout1.addWidget(self.reso_20)
        self.resolution_V_layout1.addWidget(self.reso_30)
        self.resolution_V_layout1.addWidget(self.reso_40)
        self.resolution_V_layout2 = QVBoxLayout()
        self.resolution_V_layout2.addWidget(self.reso_50)
        self.resolution_V_layout2.addWidget(self.reso_60)
        self.resolution_V_layout2.addWidget(self.reso_70)
        self.resolution_layout.addLayout(self.resolution_V_layout1)
        self.resolution_layout.addLayout(self.resolution_V_layout2)
        self.resolution.setLayout(self.resolution_layout)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.resolution)
        self.layout.addLayout(self.button_layout)
        
        self.operation_box = QGroupBox("Operation Parameter")
        self.operation_box.setLayout(self.layout)
        
        
        #self.setLayout(layout)
        # Sample 3D topography animation
        self.graphical_box = QGroupBox("Sample 3D topography")
        self.graphical_layout = QVBoxLayout()
        #main_widget.setObjectName("Sample 3D topography")
        #self.setCentralWidget(self.main_widget)
        
        ### self.frame to contain the self.canvas
        self.frame = QFrame()
        
        #frame.setObjectName("Sample 3D topography")
        self.frame.setFrameShape(QFrame.WinPanel)
        #create horizontalLayoutNew
        self.horizontalLayoutNew = QHBoxLayout(self.frame)
        
        # canvas
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        
        
        #end of canvas
        self.horizontalLayoutNew.addWidget(self.canvas, 2)
        # end of horizontalLayout
        
        self.graphical_layout.addWidget(self.frame, 2)
        self.frame_2 = QFrame()
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        
        self.horizontalLayout2 = QHBoxLayout(self.frame_2)
        self.horizontalLayout2.setContentsMargins(0,0,0,0)
        self.horizontalLayout2.setSpacing(0)
        
        self.pushButton = QPushButton(self.frame_2) ##, clicked = lambda: self.plot())
        self.pushButton.clicked.connect(self.plot)
        
        self.pushButton.setObjectName("pushButton")
        self.pushButton.setText("Click here to view 3D graph")
        self.timer = QTimer()
        self.timer.timeout.connect(self.pushButton.click)
            
        
        #pushButton.clicked.connect(self.plot())
        self.horizontalLayout2.addWidget(self.pushButton, 0)
        self.graphical_layout.addWidget(self.pushButton, 0)
        #self.graphical_layout.addWidget(self.horizontalLayout2, 0)
        #self.graphical_layout.addWidget(self.frame_2, 0)
        
        
        self.graphical_box.setLayout(self.graphical_layout)
        
        #frame.setObjectName("Sample 3D topography")
        """
        scene = QGraphicsScene()
        scene.setObjectName("Sample 3D topography")
        graphicView = QGraphicsView(scene, self)
        graphicView.setObjectName("Sample 3D topography")
        graphicView.setGeometry(0, 0, 600, 600)
        """
        
        
        self.layout_com = QHBoxLayout()
        self.layout_com.addWidget(self.operation_box)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
        #layout_com.addWidget(graphicView)
        self.layout_com.addWidget(self.graphical_box)
        self.setLayout(self.layout_com)
        
        self.errorBox = QMessageBox()
        self.errorBox.setWindowTitle("Exception Occurred")
    def run_program(self):
        
        
        
        self.worker1 = WorkerThread()
        self.worker1.start()
        
        slot = 0
        self._client.program_execute(slot)
        
       
            
    def stop_program(self):
        r = self._client.program_terminate()
        logger.debug('Program terminate returns: %s', r) 
    
    def plot(self):
        
        self.figure.clear()
        ax = plt.axes(projection = '3d')
        ax.set_xlabel("Fast-scan axis")
        ax.set_ylabel("Slow-scan axis")
        ax.set_ylim(0, 100)
        ax.set_xlim(0, 90)
        ax.set_zlim(0, 10)
        ax.set_zlabel("Height")
        try:
            X_to_plot, Y_to_plot, Z_to_plot = read_data(data_file)    
              
        except pandas.errors.EmptyDataError:
            
            self.errorBox.setIcon(QMessageBox.Warning)
            self.errorBox.setText(f"This file is empty or does not contain any columns!")            
            self.errorBox.exec_()
        except FileNotFoundError: 
            self.errorBox.setIcon(QMessageBox.Critical)
            self.errorBox.setText(f"The file not found!")
            self.errorBox.exec_()        
        except ValueError:
            self.errorBox.setIcon(QMessageBox.Critical)
            self.errorBox.setText(f"zero-size array to reduction operation maximum which has no identity!")
            self.errorBox.exec_()
        else:
                   #ax.plot_surface(X_to_plot, Y_to_plot, Z_to_plot, cmap = 'plasma')
            try:
                ax.plot_trisurf(X_to_plot,Y_to_plot, Z_to_plot, cmap='plasma', edgecolor='none')
            except ValueError:
                self.errorBox.setIcon(QMessageBox.Critical)
                self.errorBox.setText(f"Array must have a length of at least 3")
                self.errorBox.exec_()
            except RuntimeError as e:
                self.errorBox.setIcon(QMessageBox.Critical)
                self.errorBox.setText(f"e")
                self.errorBox.exec_()
                    
        #ax.plot_wireframe(X_to_plot,Y_to_plot, Z_to_plot, cmap= 'plasma')
        #ax.contourf(X_to_plot,Y_to_plot, Z_to_plot, zdir='y', offset = 0.5, cmap = 'plasma' )
            
            
        self.canvas.draw()
        #cid = self.canvas.mpl_connect('scroll_event', lambda event: ax.set_xlim(event.xdata, event.ydata))
        self.timer.start(10000)

class WorkerThread(QThread):
    def run(self):
        while True:
            open_log(log_filename,data_file, dt_now_test )
            time.sleep(5)

class WorkerThread_plot_timer(QThread):
    def __init__(self, button, parent=None) -> None:
        super().__init__(parent)
        self.button = button
    def run(self):
        while True:
            self.timer = QTimer()
            self.timer.timeout.connect(self.button.click)
            self.timer.start(5000)
        
            
        

if __name__ == '__main__':
    
    
    hc = HubClient()
    monitor = HubMonitor(hc)
    monitor.logger = ProgramHubLogger('logs/program')
    #open_log(log_filename, data_file)
    app = QApplication(sys.argv)      
    window = MainWindow(hc, monitor)
    
     
    window.show()
    
    #p1 = mp.Process(target = open_log, *args = (log_filename,data_file, dt_now,))
    #p2 = mp.Process(target = read_data, *args = (data_file))
    
    
    hc.start()
    
    sys.exit(app.exec())


        
        




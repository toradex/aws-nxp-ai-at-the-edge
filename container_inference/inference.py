import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_foreign('cairo')
from gi.repository import GLib, Gst, GstApp
import sys, os, time, re,signal
from time import time, sleep
from dlr import DLRModel
import numpy as np
import gc
import cv2
from queue import Queue
import threading

im_width_out = 320
im_height_out = 240
#im_width_out = 2592
#im_height_out = 1944

net_input_size= 224

class_names =['shell','elbow','penne','tortellini','farfalle']
colors=[(0xFF,0xFF,0x00),(0xFF,0x66,0x00),(0xFF,0x00,0x00),(0x99,0xFF,0x00),(0x00,0x00,0xFF),(0x00,0xFF,0x00)]
#colors=[(0x99,0xCC,0x00),(0xFF,0x99,0x00),(0xFF,0x33,0x00),(0x33,0xFF,0x00),(0x99,0x66,0x00),(0xFF,0xFF,0x00),(0x99,0x00,0x00)]

#*************************START FLASK**********************
history = Queue(1000)
from flask import Flask
from flask_restful import Resource, Api
from flask_cors import CORS, cross_origin
app = Flask(__name__)
# add cors
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
api = Api(app)

@app.route('/inference/')
@cross_origin()
def inference_web():
    global last_inference
    str_history = '{"history": ['
    while history.qsize()>0 :
        history_item = history.get(block=True, timeout=None)
        str_history = str_history + history_item.json()
        if history.qsize()>0 :
            str_history = str_history + ','
    str_history = str_history + ']}'
    return str_history

@app.route('/inference/last')
@cross_origin()
def last_inference_web():
    global last_inference
    return last_inference.json()

class result:
    def __init__(self, score, object,xmin,ymin,xmax,ymax,time):
        self.score = score
        self.object = object
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax
        self.time = time
    def json(self):
       return ('{"score": "%s","object": "%s","xmin": "%s","ymin": "%s","xmax": "%s","ymax": "%s"}'
                   %(self.score,self.object,self.xmin,self.ymin,self.xmax,self.ymax))

class inference:
    def __init__(self, timestamp, inference_time,results):
        self.timestamp = timestamp
        self.inference_time = inference_time
        self.results = results
    def json(self):
        results = ('{"timestamp": "%s","inference_time": "%s",'
                    %(self.timestamp,self.inference_time))
        results = results + '"last":['
        for i in range(len(self.results)):
            results = results + self.results[i].json()
            if(i<len(self.results)-1):
                results = results + ','
        results = results +']}'
        return results
last_inference = inference(0,0,[])
#************************* END FLASK **********************

# Inference
def pasta_detection(img):
    global last_inference
    #******** INSERT YOUR INFERENCE HERE ********
    buf=img.astype('float64')

    # Mean and Std deviation of the RGB colors from dataset
    redmean=255*0.4401859057358472
    gremean=255*0.5057172186334968
    blumean=255*0.5893379173439015
    redstd=255*0.24873837809532068
    grestd=255*0.17898858615083552
    blustd=255*0.3176466480114065

    #crop input image from the center
    net_input = buf[int(buf.shape[0]/2-net_input_size/2):int(buf.shape[0]/2+net_input_size/2), \
    		int(buf.shape[1]/2-net_input_size/2):int(buf.shape[1]/2+net_input_size/2),:]

    #prepare image to input
    net_input = net_input.reshape((net_input_size*net_input_size ,3))
    net_input =np.transpose(net_input)
    net_input[0,:] = net_input[0,:]-redmean
    net_input[0,:] = net_input[0,:]/redstd
    net_input[1,:] = net_input[1,:]-gremean
    net_input[1,:] = net_input[1,:]/grestd
    net_input[2,:] = net_input[2,:]-blumean
    net_input[2,:] = net_input[2:]/blustd

    #Run the model
    t1 = time()
    outputs = model.run({'data': net_input})
    t2 = time()
    last_inference_time = t2-t1
    objects=outputs[0][0]
    scores=outputs[1][0]
    bounding_boxes=outputs[2][0]

    i = 0

    #***********FLASK*******
    result_set=[]
    #***********END OF FLASK*******
    while (scores[i]>0.6):

        #***********FLASK*******
        this_object=class_names[int(objects[i])]
        this_result = result(
            score= scores[i],
            object= this_object,
            xmin= bounding_boxes[i][0]+160-(net_input_size/2),
            xmax= bounding_boxes[i][2]+160-(net_input_size/2),
            ymin= bounding_boxes[i][1]+120-(net_input_size/2),
            ymax= bounding_boxes[i][3]+120-(net_input_size/2),
            time=t2)
        result_set.append(this_result)
        #***********END OF FLASK*******

        x1= int(bounding_boxes[i][0]+160-(net_input_size/2))
        x2= int(bounding_boxes[i][2]+160-(net_input_size/2))
        y1= int(bounding_boxes[i][1]+120-(net_input_size/2))
        y2= int(bounding_boxes[i][3]+120-(net_input_size/2))
        object_id=int(objects[i])
        cv2.rectangle(img,(x2,y2),(x1,y1),colors[object_id%len(colors)],2)
        cv2.rectangle(img,(x1+50,y2+15),(x1,y2),colors[object_id%len(colors)],cv2.FILLED)
        cv2.putText(img,class_names[object_id],(x1,y2+10), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(255,255,255),1,cv2.LINE_AA)
        i=i+1
    #cv2.rectangle(img,(115,13),(0,0),(0,0,255),cv2.FILLED)
    cv2.putText(img,"inf. time: %.3fs"%last_inference_time,(3,12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,(255,255,255),1,cv2.LINE_AA)

    #***********FLASK*******
    last_inference = inference(t1,last_inference_time,result_set)
    if(history.full()==False): #FLASK
       history.put(last_inference, block=True, timeout=None)
    #***********END OF FLASK*******

    #******** END OF YOUR INFERENCE CODE ********

# Pipeline 1 output
def get_frame(sink, data):
    global appsource

    sample = sink.emit("pull-sample")
    global_buf = sample.get_buffer()

    caps = sample.get_caps()
    im_height_in = caps.get_structure(0).get_value('height')
    im_width_in = caps.get_structure(0).get_value('width')

    mem = global_buf.get_all_memory()
    success, arr = mem.map(Gst.MapFlags.READ)
    if success == True:
        img = np.ndarray((im_height_in,im_width_in,3),buffer=arr.data,dtype=np.uint8)
        img = cv2.resize(img, (im_width_out, im_height_out), interpolation = cv2.INTER_AREA)
        pasta_detection(img)
    img = np.array(img,dtype=np.uint8)
    img = np.reshape(img,(im_width_out*im_height_out*3))
    gst_buf = Gst.Buffer.new_allocate(None, im_width_out*im_height_out*3, None)
    gst_buf.fill(0, img)
    appsource.push_buffer(gst_buf)
    mem.unmap(arr)
    gc.collect()
    return Gst.FlowReturn.OK

def main():
    print("Pasta Demo inference started\n")
    # SagemakerNeo init
    global model
    global appsource
    global pipeline1
    global pipeline2

    model = DLRModel('./model', 'cpu')

    # Gstreamer Init
    Gst.init(None)

    try:
        f = open("/dev/video0")
        input_src="v4l2src device=/dev/video0"
        f.close()
    except FileNotFoundError:
        input_src="v4l2src device=/dev/video4"

    pipeline1_cmd=input_src+" ! queue ! \
        videoconvert ! video/x-raw,format=RGB ! \
        appsink sync=False name=sink max-buffers=1 drop=True max-buffers=1 \
        qos=False sync=False emit-signals=True"

    pipeline1 = Gst.parse_launch(pipeline1_cmd)
    appsink = pipeline1.get_by_name('sink')
    appsink.connect("new-sample", get_frame, appsink)

    try:
        f = open("/dev/video14")
        output_sink="v4l2sink sync=False device=/dev/video14"
        f.close()
    except FileNotFoundError:
        output_sink="autovideosink"

    pipeline2_cmd = "appsrc name=appsource1 is-live=True block=True ! \
        video/x-raw,format=RGB,width="+str(im_width_out)+",height="+str(im_height_out)+",\
        framerate=10/1,interlace-mode=(string)interleaved ! \
        videoconvert ! videoconvert ! " + output_sink

    pipeline2 = Gst.parse_launch(pipeline2_cmd)
    appsource = pipeline2.get_by_name('appsource1')

    pipeline1.set_state(Gst.State.PLAYING)
    bus1 = pipeline1.get_bus()
    pipeline2.set_state(Gst.State.PLAYING)
    bus2 = pipeline2.get_bus()

    # Main Loop
    while True:
        message = bus1.timed_pop_filtered(10000, Gst.MessageType.ANY)
        if message:
            if message.type == Gst.MessageType.ERROR:
                # print("bus 1: ",message.parse_error())
                # Free resources
                pipeline1.set_state(Gst.State.NULL)
                pipeline2.set_state(Gst.State.NULL)
                break

        message = bus2.timed_pop_filtered(10000, Gst.MessageType.ANY)
        if message:
            if message.type == Gst.MessageType.ERROR:
                # print("bus 1: ",message.parse_error())
                # Free resources
                pipeline1.set_state(Gst.State.NULL)
                pipeline2.set_state(Gst.State.NULL)
                break

    # Free resources
    pipeline1.set_state(Gst.State.NULL)
    pipeline2.set_state(Gst.State.NULL)

def signal_handler(signal, frame):
    global pipeline1
    global pipeline2
    pipeline1.set_state(Gst.State.NULL)
    pipeline2.set_state(Gst.State.NULL)
    print("exiting...")
    sleep(10)
    sys.exit(0)

if (__name__ == "__main__"):
    signal.signal(signal.SIGINT, signal_handler)
    thread1 = threading.Thread(target = main)
    thread1.start()

if __name__ == '__main__':
    print("Flask working well")
    app.run(host='0.0.0.0', port='5003')
else:
    print(__name__)
    print("Flask not working")

# if __name__ == "__main__":
#     main()

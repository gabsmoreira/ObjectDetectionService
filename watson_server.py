from flask import Flask, request, jsonify, Response
import json
import numpy
from gluoncv import model_zoo, data, utils
import os

MODEL = model_zoo.get_model('yolo3_darknet53_coco', pretrained=True)

def identify(frame, percentage_limit=0.6):
  results = []
  x, img = data.transforms.presets.yolo.load_test(frame, short=512)
  class_IDs, scores, boxes = MODEL(x)
  scores = scores.asnumpy()
  class_IDs = class_IDs.asnumpy()
  boxes = boxes.asnumpy()
  for j in range(len(class_IDs[0])):
    if(scores[0][j][0] > percentage_limit):
      index = int(class_IDs[0][j][0])
      results.append([MODEL.classes[index], scores[0][j][0].astype(float), boxes[0][j].astype(float).tolist()])
  # return results, boxes
  return results

app = Flask(__name__)
@app.route('/')
def hello_world():
  return 'Hello, World!'

@app.route('/predict', methods = ['GET'])
def predict_route():
  if request.method == 'GET':
    json_response = {}
    image_url = request.args.get('image_url', default = None, type = str)
    percentage_limit = request.args.get('limit', default = 0.4, type = float)
    print(f'Requesting for {image_url}')
    print(f'Limit is {percentage_limit}')
    try:
      im_fname = utils.download(image_url, path='image.jpg')
    except Exception as e:
      print(f'Could not resolve URL: {image_url}')
      print(e)
      return Response(status=403)

    results = identify(im_fname, percentage_limit=percentage_limit)
    for i, result in enumerate(results):
      json_response[str(i)] = result
    os.system('rm -rf image.jpg')
    return jsonify(json_response)

@app.route('/healthcheck', methods = ['GET'])
def healthcheck():
  return Response(status=200)
  
app.run(host='0.0.0.0', port=5000)
  
      
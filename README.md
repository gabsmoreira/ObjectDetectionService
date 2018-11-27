# ObjectDetectionService

The project is a cloud microservice that deploys a load balancer with 3 instances on AWS.
The 3 instances are running a Flask service that is capable of detecting objects of a given image link.
The service runs on port ```5000``` on each instance.

## The object detection API

### Routes
  #### /predict
  Params: 
      
      image_url=https://raw.githubusercontent.com/zhreshold/mxnet-ssd/master/data/demo/dog.jpg
    
  Response: 
  
  ```json 
  {
      "0": [
          "dog",
          0.9919527769088745,
          [
              116.5364761352539,
              201.3323974609375,
              281.90325927734375,
              482.09088134765625
          ]
      ],
      "1": [
          "bicycle",
          0.9600397944450378,
          [
              93.92974853515625,
              107.73939514160156,
              504.75128173828125,
              375.7542724609375
          ]
      ],
      "2": [
          "truck",
          0.6226974725723267,
          [
              416.788330078125,
              69.80065155029297,
              615.0179443359375,
              148.89007568359375
          ]
      ]
  }
```


## How to run
1) Put your credentials on ```credentials.json```.

2) Run ```pip install boto3```.

3) Run ```python deploy.py```.

4) Wait for instances to warm up.

5) Run ```<load_balancer_ip>:5000/predict?image_url=<image_link>``` on your browser.


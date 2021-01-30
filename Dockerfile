FROM tensorflow/tensorflow:2.3.0-gpu-jupyter

# ADD ./requirements.txt .

# RUN pip install -r requirements.txt
ENV PATH="/.local/bin:${PATH}"

RUN mkdir .cache
RUN apt-get update -y && apt-get install git wget -y

EXPOSE 8888 6006

# syntax=docker/dockerfile:1

FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

WORKDIR /home/app
COPY . .

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip libsndfile1-dev ffmpeg
RUN python3 -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
RUN python3 -m pip install -r requirements.txt

ENV HYDRA_FULL_ERROR=1
ENV DIR_LOGS=/home/app/logs
ENV DIR_DATA=/home/app/data
RUN mkdir -p $DIR_LOGS
RUN mkdir -p $DIR_DATA

CMD python3 train.py exp=base_test

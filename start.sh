#! /bin/sh

PORT=$1
TAG=icodegen

if [ $# -eq 2 ]; then
	if [ "$2" = "--build" ]; then
		# Build the docker container
		docker build -t $TAG .
	fi
fi


# docker run --gpus all -d -it -p $PORT:8888 -u $(id -u):$(id -g)
docker run --gpus all -d -u $(id -u):$(id -g) -v /semeru/icode_gen:/tf/data  -v $(pwd):/tf/main -p $PORT:8888 --name $TAG-$(whoami) $TAG
# Run the docker container. Add additional -v if
# you need to mount more volumes into the container
# Also, make sure to edit the ports to fix your needs.
# docker run --gpus all -d -it -p $PORT:8888 -v $(pwd):/home/jovyan/work \
#  -e GRANT_SUDO=yes -e JUPYTER_ENABLE_LAB=yes -e NB_UID="$(id -u)" \
#  -e NB_GID="$(id -g)" --user root --restart always --name $TAG \
#  semerulab/datascience:dev-cuda101

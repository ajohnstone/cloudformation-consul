#!/bin/sh
set -e
REGION=us-east-1 # N. Virginia
export AWS_DEFAULT_REGION=$REGION
VPC_NAME=$REGION-dev
STACK_NAME=$VPC_NAME-consul

PARAMS_FILE=./cf/$STACK_NAME.json

./cf/consul_formation.py > ./cf/consul_formation.cftemplate

ruby ./cf/aws_parameter_lookup.rb $VPC_NAME $REGION > ./cf/$STACK_NAME.json

aws cloudformation create-stack \
--stack-name $STACK_NAME \
--region $REGION \
--template-body file://cf/consul_formation.cftemplate \
--parameters file://$PARAMS_FILE

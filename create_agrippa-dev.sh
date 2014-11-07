#!/bin/bash
set -e
REGION=us-east-1 # Virginia
export AWS_DEFAULT_REGION=$REGION
VPC_NAME=$REGION-dev
STACK_NAME=$VPC_NAME-agrippa

PARAMS_FILE=$STACK_NAME.json
CFTEMPLATE=$STACK_NAME.cftemplate

CLUSTER=dev

ruby aws_parameter_lookup.rb $VPC_NAME $REGION $CLUSTER > $PARAMS_FILE
python consul_formation.py > $CFTEMPLATE

aws cloudformation create-stack \
--stack-name $STACK_NAME \
--region $REGION \
--template-body file://$CFTEMPLATE \
--parameters file://$PARAMS_FILE \
--capabilities CAPABILITY_IAM

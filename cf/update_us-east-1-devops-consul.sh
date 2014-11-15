#!/bin/sh
set -e
REGION=us-east-1 # N. Virginia
export AWS_DEFAULT_REGION=$REGION
VPC_NAME=$REGION-devops
STACK_NAME=$VPC_NAME-consul

PARAMS_FILE=./cf/$STACK_NAME.json

ruby ./cf/yaml_to_json.rb ./cf/consul_formation.yml > ./cf/consul_formation.cftemplate

ruby ./cf/aws_parameter_lookup.rb $VPC_NAME $REGION > $PARAMS_FILE

aws cloudformation update-stack \
--stack-name $STACK_NAME \
--region $REGION \
--template-body file://cf/consul_formation.cftemplate \
--parameters file://$PARAMS_FILE

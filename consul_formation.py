#!/usr/bin/python
from troposphere import *

import troposphere.iam as iam
import troposphere.autoscaling as autoscaling
import troposphere.ec2 as ec2
import troposphere.cloudformation as cloudformation
import troposphere.elasticloadbalancing as elb

ENDLINE = "ENDLINE"

def splice_ref(lines, pattern, replacement):
    matching_lines = filter(lambda x: isinstance(x, str) and x.find(pattern) != -1, lines)
    out = []
    for mixed in lines:
        if isinstance(mixed, str) and mixed in matching_lines:
            tokens = mixed.split(pattern)

            for i in range(0, len(tokens) - 1):
                out.append(tokens[i])
                out.append(replacement)
            out.append(tokens[len(tokens) - 1])
        else:
            out.append(mixed)
    return out

template = Template()

template.description = "Start a Consul cluster"

# Parameters
instance_type = template.add_parameter(Parameter(
    "InstanceType",
    Description = "EC2 instance type",
    Type = "String",
    Default = "m3.medium",
    AllowedValues = [
        "m3.medium",
        "m3.large"
    ],
    ConstraintDescription = "must be a valid EC2 instance type."
))

environment = template.add_parameter(Parameter(
    "Environment",
    Description = "Environment (example: dev, prod)",
    Type = "String",
    Default = "dev"
))

keyname = template.add_parameter(Parameter(
    "KeyName",
    Description = "Name of an existing EC2 KeyPair to enable SSH "
                "access to the instance",
    Type = "String"
))

cluster_size = template.add_parameter(Parameter(
    "ClusterSize",
    Description = "Number of nodes to launch",
    Type = "Number",
    Default = "3"
))

subnets = template.add_parameter(Parameter(
    "Subnets",
    Description = "List of VPC subnet IDs for the cluster. Note: must match up with the passed AvailabilityZones",
    Type = "CommaDelimitedList"
))

vpc_id = template.add_parameter(Parameter(
    "VpcId",
    Description = "VPC associated with the provided subnets",
    Type = "String"
))

admin_security_group = template.add_parameter(Parameter(
    "AdminSecurityGroup",
    Description = "Existing security group that should be granded administrative access to Consul (e.g., 'sg-123456')",
    Type = "String"
))

availability_zones = template.add_parameter(Parameter(
    "AvailabilityZones",
    Description = "(Optional) If passed, only launch nodes in these AZs (e.g., 'us-east-1a,us-east-1b'). Note: these must match up with the passed Subnets.",
    Type = "CommaDelimitedList",
    Default = ""
))

# Mappings

region_map = template.add_mapping('RegionMap', {
    "us-east-1":      {"AMI": "ami-fe01b796"},
    "ap-southeast-2": {"AMI": "ami-c16d00fb"},
})

# Conditions

use_all_availability_zones = template.add_condition(
    "UseAllAvailabilityZones", 
    Equals(
        Join("", Ref(availability_zones)),
        ""
    )
)

# Resources

consul_instance_role = template.add_resource(iam.Role(
    "ConsulInstanceRole",
    AssumeRolePolicyDocument = {
        "Statement" : {
            "Effect" : "Allow",
            "Principal" : {
                "Service": [ "ec2.amazonaws.com" ]
            },
            "Action": [ "sts:AssumeRole" ]
        }
    },
    Path = "/ConsulInstanceRole/",
    Policies = [
        iam.Policy(
            PolicyName="ConsulInstancePolicy",
            PolicyDocument= {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [ "ec2:DescribeInstances" ],
                        "Resource": "*"
                    }
                ]
            }
        )
    ]
))

consul_instance_profile = template.add_resource(iam.InstanceProfile(
    "ConsulInstanceProfile",
    Path = "/ConsulInstanceRole/",
    Roles = [Ref(consul_instance_role)]
))

server_security_group = template.add_resource(ec2.SecurityGroup(
    "ServerSecurityGroup",
    GroupDescription = "Enable SSH and Consul access",
    VpcId = Ref(vpc_id),
    SecurityGroupIngress = [
        ec2.SecurityGroupRule(
            IpProtocol = "tcp",
            FromPort = "22",
            ToPort = "22",
            CidrIp = "10.0.0.0/8"
        )
    ]
))

security_group_ingress = template.add_resource(ec2.SecurityGroupIngress(
    "SecurityGroupIngress",
    GroupId = Ref(server_security_group),
    IpProtocol = "-1",
    FromPort = "0",
    ToPort = "65535",
    SourceSecurityGroupId = Ref(server_security_group)
))

bootstrap_load_balancer = template.add_resource(elb.LoadBalancer(
    "BootstrapLoadBalancer",
    Subnets=Ref(subnets),
    Listeners=[
        {
            "LoadBalancerPort": "8888",
            "InstancePort" : "8888",
            "Protocol" : "TCP"
        }
    ]
))

wait_handle = template.add_resource(cloudformation.WaitConditionHandle("WaitHandle"))

# Load up and process the cloud-init script

cloud_init_script = open("cloud-init.sh", 'r').read().replace("\n", "\n" + ENDLINE)

cloud_init_script_lines = cloud_init_script.split(ENDLINE)

replacements = [
    ["WAIT_HANDLE", Ref(wait_handle)],
]

for pair in replacements:
    cloud_init_script_lines = splice_ref(cloud_init_script_lines, pair[0], pair[1])

# More resources

launch_config = template.add_resource(autoscaling.LaunchConfiguration(
    "LaunchConfig",
    KeyName = Ref(keyname),
    ImageId = FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
    InstanceType = Ref(instance_type),
    IamInstanceProfile = Ref(consul_instance_profile),
    SecurityGroups = [
        Ref(server_security_group),
        Ref(admin_security_group)
    ],
    AssociatePublicIpAddress = "true",
    UserData = Base64(
        Join("", cloud_init_script_lines)
    ),
    Metadata = {
        "AWS::CloudFormation::Init" : {
            "config": {
                "files": {
                    # "/etc/consul.d/default.json" : {
                    #     "data_dir": "/var/lib/consul",
                    #     "server": True,
                    #     "bootstrap_expect": 3,
                    #     "start_join": [GetAtt(bootstrap_load_balancer, "DNSName")],
                    #     "datacenter": Ref("AWS::Region")
                    # },
                    "/etc/chef/node.json": {
                        "name": "consul-cookbook-test",
                        "run_list": [
                            "recipe[consul::_service]"
                        ],
                        "consul": {
                            "service_mode" : "cluster",
                            "servers" : [GetAtt(bootstrap_load_balancer, "DNSName")],
                            "datacenter" : Ref("AWS::Region"),
                            "bootstrap_expect": "3"
                        }
                    }
                }
            }
        }
    }
))

server_group = template.add_resource(autoscaling.AutoScalingGroup(
    "ServerGroup",
    AvailabilityZones = If(
        "UseAllAvailabilityZones",
        GetAZs("AWS::Region"),
        Ref(availability_zones)
    ),
    LaunchConfigurationName = Ref(launch_config),
    LoadBalancerNames=[Ref("BootstrapLoadBalancer")],
    MinSize = "1",
    MaxSize = "9",
    DesiredCapacity = Ref(cluster_size),
    VPCZoneIdentifier = Ref(subnets),
    Tags = [
        {"Key" : "Name", "Value" : Join("-", [Ref("AWS::Region"), Ref(environment), "consul"]), "PropagateAtLaunch" : "true"},
        {"Key" : "role", "Value" : "elasticsearch_catalog", "PropagateAtLaunch" : "true"} 
    ]
))

if __name__ == "__main__":
    print(template.to_json())
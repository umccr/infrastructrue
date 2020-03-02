from aws_cdk import (
    # For the instance
    aws_ec2 as ec2,
    # For access to ecr and s3
    aws_iam as iam,
    # Aws cdk essentials
    core
)

"""
Globals
"""


# Class definition
class GridssPurpleLynxStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Set a vpc
        vpc = ec2.Vpc.from_lookup(self, "VPC", is_default=True)
        vpc_subnets = ec2.SubnetSelection()

        # Set access policies for the instance
        policies = [
                    # Read only access for all our s3 buckets
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                    # Set the container registry policy so we can pull docker containers from our ECR repo
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                    # Allow us login by the ssm manger
                    iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
                    ]

        # Get role object with set policies
        role = iam.Role(self, "EC2Role",
                        assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                        managed_policies=policies)

        # Get volume - contains a block device volume and a block device
        volume_params = self.node.try_get_context("VOLUME")
        ebs_vol = ec2.BlockDeviceVolume.ebs(volume_size=int(volume_params["SIZE"]))
        # Place volume on a block device with a set mount point
        ebs_block_device = ec2.BlockDevice(device_name=volume_params["MOUNT_POINT"], volume=ebs_vol)

        # Run boot strap -
        """
        The code under userdata.sh completes the following steps
        1. Installs docker into ec2 instance
        2. Mounts our volume to /mnt/
        3. Pulls the gridss container from our ECR (Elastic container repository)
        4. Imports the user data
        """
        with open("user_data/user_data.sh", 'r') as user_data_h:
            user_data = ec2.UserData.custom(user_data_h.read())

        # Set instance type from ec2-type global variable
        instance_type = ec2.InstanceType(instance_type_identifier=self.node.try_get_context("EC2_TYPE"))

        # Get machine type
        machine_image = ec2.GenericLinuxImage({
              self.region: self.node.try_get_context("MACHINE_IMAGE"),  # Refer to an existing AMI type
        })

        # Get key from context
        key_name = self.node.try_get_context("KEY_NAME")

        # The code that defines your stack goes here
        # We take all of the parameters we have and place this into the ec2 instance class
        host = ec2.Instance(self,
                            id="gridss-ec2-id",
                            instance_type=instance_type,
                            instance_name="gridss-ec2-instance",
                            machine_image=machine_image,
                            vpc=vpc,
                            vpc_subnets=vpc_subnets,
                            key_name=key_name,
                            role=role,
                            user_data=user_data,
                            block_devices=[ebs_block_device]
                            )

        # Return public IP address s.t we can ssh into it
        # Note that we may return an IP prior to the user_data shell script completing so not
        # all of our goodies may be here yet
        core.CfnOutput(self, "Output",
                       value=host.instance_id)
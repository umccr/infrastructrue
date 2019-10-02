import os
import boto3
import json


def lambda_handler(event, context):
    # Log the received event
    print("Received event: " + json.dumps(event, indent=2))
    # get the Batch client ready
    batch_client = boto3.client('batch')

    # Retrieve parameters
    container_overrides = event['containerOverrides'] if event.get('containerOverrides') else {}
    parameters = event['parameters'] if event.get('parameters') else {}
    depends_on = event['dependsOn'] if event.get('dependsOn') else []
    job_queue = event['jobQueue'] if event.get('jobQueue') else os.environ.get('JOBQUEUE')
    job_definition = event['jobDefinition'] if event.get('jobDefinition') else os.environ.get('JOBDEF')
    container_mem = event['memory'] if event.get('memory') else os.environ.get('JOB_MEM')
    container_vcpus = event['vcpus'] if event.get('vcpus') else os.environ.get('JOB_VCPUS')
    data_bucket = event['dataBucket'] if event.get('dataBucket') else os.environ.get('DATA_BUCKET')
    refdata_bucket = event['refDataBucket'] if event.get('refDataBucket') else os.environ.get('REFDATA_BUCKET')

    data_wts_dir = event['dataDirWTS']
    data_wgs_dir = event['dataDirWGS']
    job_name = data_bucket + "---" + data_wts_dir.replace('/', '_').replace('.', '_')
    job_name = os.environ.get('JOBNAME_PREFIX') + '_' + job_name

    # create and submit a Batch job request
    container_overrides['environment'] = [
        {'name': 'S3_WTS_INPUT_DIR', 'value': data_wts_dir},
        {'name': 'S3_WGS_INPUT_DIR', 'value': data_wgs_dir},
        {'name': 'S3_DATA_BUCKET', 'value': data_bucket},
        {'name': 'S3_REFDATA_BUCKET', 'value': refdata_bucket}
    ]

    if container_mem:
        container_overrides['memory'] = int(container_mem)
    if container_vcpus:
        container_overrides['vcpus'] = int(container_vcpus)
        parameters['vcpus'] = container_vcpus

    print("jobName: " + job_name)
    print("containerOverrides: ")
    print(container_overrides)
    print("jobDefinition: ")
    print(job_definition)
    response = batch_client.submit_job(
        dependsOn=depends_on,
        containerOverrides=container_overrides,
        jobDefinition=job_definition,
        jobName=job_name,
        jobQueue=job_queue,
        parameters=parameters
    )

    # Log response from AWS Batch
    print("Response: " + json.dumps(response, indent=2))
    # Return the jobId
    event['jobId'] = response['jobId']
    return event
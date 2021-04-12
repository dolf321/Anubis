import logging
import os
import time

import kubernetes
from kubernetes import config, client

from anubis.models import Config, Submission
from anubis.utils.data import is_debug
from anubis.utils.logger import logger


def create_pipeline_job_obj(client, submission):
    """
    Create pipeline kube api object.

    :param client:
    :param submission:
    :return:
    """

    requirements = {
        'limits': {"cpu": "2", "memory": "750Mi"},
        'requests': {"cpu": "500m", "memory": "100Mi"},
    }

    if is_debug():
        requirements = {}

    container = client.V1Container(
        name="pipeline",
        image=submission.assignment.pipeline_image,
        image_pull_policy=os.environ.get("IMAGE_PULL_POLICY", default="Always"),
        env=[
            client.V1EnvVar(name="NETID", value=submission.owner.netid),
            client.V1EnvVar(name="TOKEN", value=submission.token),
            client.V1EnvVar(name="COMMIT", value=submission.commit),
            client.V1EnvVar(name="GIT_REPO", value=submission.repo.repo_url),
            client.V1EnvVar(name="SUBMISSION_ID", value=str(submission.id)),
            client.V1EnvVar(
                name="GIT_CRED",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name="git", key="credentials"
                    )
                ),
            ),
        ],
        resources=client.V1ResourceRequirements(**requirements),
    )
    # Create and configure a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels={"app": "submission-pipeline", "role": "submission-pipeline-worker"}
        ),
        spec=client.V1PodSpec(restart_policy="Never", containers=[container]),
    )
    # Create the specification of deployment
    spec = client.V1JobSpec(
        template=template, backoff_limit=3, ttl_seconds_after_finished=30
    )
    # Instantiate the job object
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name="submission-pipeline-{}-{}".format(submission.id, int(time.time()))
        ),
        spec=spec,
    )

    return job


def cleanup_jobs(batch_v1) -> int:
    """
    Runs through all jobs in the namespace. If the job is finished, it will
    send a request to the kube api to delete it. Number of active jobs is
    returned.

    :param batch_v1:
    :return: number of active jobs
    """
    jobs = batch_v1.list_namespaced_job("anubis")
    active_count = 0
    for job in jobs.items:
        if job.status.succeeded is not None and job.status.succeeded >= 1:
            logging.info("deleting namespaced job {}".format(job.metadata.name))
            try:
                batch_v1.delete_namespaced_job(
                    job.metadata.name,
                    job.metadata.namespace,
                    propagation_policy="Background",
                )
            except kubernetes.client.exceptions.ApiException:
                pass
        else:
            active_count += 1

    return active_count


def create_submission_pipeline(submission_id: str):
    """
    This function should launch the appropriate testing container
    for the assignment, passing along the function arguments.

    :param submission_id: submission.id of to test
    """
    from anubis.app import create_app
    from anubis.utils.rpc import enqueue_autograde_pipeline

    app = create_app()

    logger.info(
        "Starting submission {}".format(submission_id),
        extra={
            "submission_id": submission_id,
        },
    )

    with app.app_context():
        max_jobs = Config.query.filter(Config.key == "MAX_JOBS").first()
        max_jobs = int(max_jobs.value) if max_jobs is not None else 10
        submission = Submission.query.filter(Submission.id == submission_id).first()

        if submission is None:
            logger.error(
                "Unable to find submission rpc.test_repo",
                extra={
                    "submission_id": submission_id,
                },
            )
            return

        if submission.build is None:
            submission.init_submission_models()

        logger.debug(
            "Found submission {}".format(submission_id),
            extra={"submission": submission.data},
        )

        # Initialize kube client
        config.load_incluster_config()
        batch_v1 = client.BatchV1Api()

        # Cleanup finished jobs
        active_jobs = cleanup_jobs(batch_v1)

        if active_jobs > max_jobs:
            logger.info(
                "TOO many jobs - re-enqueue {}".format(submission_id),
                extra={"submission_id": submission_id},
            )
            enqueue_autograde_pipeline(submission_id)
            exit(0)

        # Create job object
        job = create_pipeline_job_obj(client, submission)

        # Log
        logger.debug("creating pipeline job: " + job.to_str())

        # Send to kube api
        batch_v1.create_namespaced_job(body=job, namespace="anubis")

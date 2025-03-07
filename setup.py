import boto3
import json

# 🔹 Change these variables as needed
AWS_REGION = "us-east-1"
BUCKET_NAME = "audio-transcriber-ingress-bucket"
QUEUE_NAME = "audio-transcriber-ingress-queue"
IAM_USER_NAME = "audio-transcriber-ingress-user"
IAM_POLICY_NAME = "AudioTranscriberIngressPolicy"

# Initialize AWS Clients
s3 = boto3.client("s3", region_name=AWS_REGION)
sqs = boto3.client("sqs", region_name=AWS_REGION)
iam = boto3.client("iam")

def create_s3_bucket():
    """Create an S3 bucket, handling region-specific constraints."""
    try:
        print(f"Creating S3 bucket: {BUCKET_NAME}...")

        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)  # No LocationConstraint needed
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION}
            )

        print("✅ S3 bucket created!")
    except Exception as e:
        print(f"⚠️ Error creating S3 bucket: {e}")

def create_sqs_queue():
    """Create an SQS queue with 5-minute visibility timeout and 14-day retention."""
    try:
        print(f"Creating SQS queue: {QUEUE_NAME}...")

        response = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={
                "VisibilityTimeout": "300",  # 5 minutes
                "MessageRetentionPeriod": "1209600"  # 14 days
            }
        )
        
        queue_url = response["QueueUrl"]
        queue_attributes = sqs.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["QueueArn"]
        )
        queue_arn = queue_attributes["Attributes"]["QueueArn"]
        print(f"✅ SQS queue created! ARN: {queue_arn}")
        return queue_url, queue_arn
    except Exception as e:
        print(f"⚠️ Error creating SQS queue: {e}")

def attach_sqs_policy(queue_arn):
    """Attach an IAM policy to allow S3 to send messages to SQS."""
    sqs_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {"ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{BUCKET_NAME}"}}
            }
        ]
    }
    print("🔹 Setting SQS policy to allow S3 events...")
    queue_url, _ = create_sqs_queue()
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={"Policy": json.dumps(sqs_policy)}
    )
    print("✅ SQS policy set!")

def configure_s3_notifications(queue_arn):
    """Configure S3 event notifications to send messages to SQS."""
    s3_notification_config = {
        "QueueConfigurations": [
            {
                "QueueArn": queue_arn,
                "Events": ["s3:ObjectCreated:*"]
            }
        ]
    }
    print("🔹 Configuring S3 event notifications...")
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration=s3_notification_config
    )
    print("✅ S3 event notifications configured!")

def create_iam_user(queue_arn):
    """Create an IAM user with access to upload to S3 and process SQS messages."""
    try:
        print(f"Creating IAM user: {IAM_USER_NAME}...")
        iam.create_user(UserName=IAM_USER_NAME)

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:PutObject", "s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{BUCKET_NAME}/*"]
                },
                {
                    "Effect": "Allow",
                    "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
                    "Resource": f"arn:aws:sqs:{AWS_REGION}:*: {QUEUE_NAME}"
                }
            ]
        }

        print(f"Creating IAM policy: {IAM_POLICY_NAME}...")
        policy_response = iam.create_policy(
            PolicyName=IAM_POLICY_NAME,
            PolicyDocument=json.dumps(policy_document)
        )
        policy_arn = policy_response["Policy"]["Arn"]

        print("Attaching policy to user...")
        iam.attach_user_policy(UserName=IAM_USER_NAME, PolicyArn=policy_arn)

        print("Creating access key for user...")
        access_key = iam.create_access_key(UserName=IAM_USER_NAME)

        print("✅ IAM user and policy created successfully!")
        print("🔑 Access Key ID:", access_key["AccessKey"]["AccessKeyId"])
        print("🔑 Secret Access Key:", access_key["AccessKey"]["SecretAccessKey"])

    except Exception as e:
        print(f"⚠️ Error creating IAM user: {e}")

def main():
    """Run all setup steps."""
    create_s3_bucket()
    queue_url, queue_arn = create_sqs_queue()
    attach_sqs_policy(queue_arn)
    configure_s3_notifications(queue_arn)
    create_iam_user(queue_arn)
    print("🚀 AWS setup complete!")

if __name__ == "__main__":
    main()

import boto3
from botocore.config import Config

class S3Service:
    def __init__(self, access_key, secret_key, region):
        # Force s3v4 and virtual-host addressing for special characters
        s3_config = Config(
            region_name=region,
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'}
        )
        
        self.client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=s3_config
        )

    def get_actual_region(self, bucket_name):
        """Verifies where the bucket actually lives."""
        try:
            loc = self.client.get_bucket_location(Bucket=bucket_name)['LocationConstraint']
            # AWS returns None or "US" for us-east-1
            return loc if loc and loc != "US" else "us-east-1"
        except Exception:
            return None

    def list_files(self, bucket_name):
        response = self.client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []

    def upload(self, bucket_name, file_obj, filename, content_type):
        self.client.upload_fileobj(
            file_obj, 
            bucket_name, 
            filename, 
            ExtraArgs={"ContentType": content_type}
        )

    def get_url(self, bucket_name, filename):
        return self.client.generate_presigned_url(
            'get_object', 
            Params={'Bucket': bucket_name, 'Key': filename}, 
            ExpiresIn=3600
        )

    def delete(self, bucket_name, filename):
        self.client.delete_object(Bucket=bucket_name, Key=filename)
import boto3
import sys
import ipaddress
import time

# --- הגדרות קבועות ---
LT_NAME = "MyFinalTemplate"
REGION = "us-east-1"
INSTANCE_TYPE = "t2.micro"

# שם ASG דינמי כדי למנוע התנגשויות עם מחיקות קודמות
ASG_NAME = f'aws-project-asg-{int(time.time())}'
NLB_NAME = 'aws-project-nlb'
TG_NAME = 'aws-project-tg'

# יצירת Clients ל-AWS
ec2 = boto3.client('ec2', region_name=REGION)
elbv2 = boto3.client('elbv2', region_name=REGION)
asg = boto3.client('autoscaling', region_name=REGION)

def get_latest_ami():
    """מאתר אוטומטית את ה-AMI הכי חדש שנוצר על ידך (self)"""
    print("🔍 מחפש את ה-AMI האחרון שיצרת...")
    try:
        images = ec2.describe_images(
            Owners=['self'],
            Filters=[{'Name': 'state', 'Values': ['available']}]
        )['Images']
        
        if not images:
            print("❌ שגיאה: לא מצאתי AMI. וודא שיצרת אימג' מהשרת המקורי.")
            sys.exit(1)
            
        latest_ami = sorted(images, key=lambda x: x['CreationDate'], reverse=True)[0]
        print(f"✅ נמצא AMI מעודכן: {latest_ami['ImageId']} ({latest_ami['Name']})")
        return latest_ami['ImageId']
    except Exception as e:
        print(f"❌ תקלה באיתור ה-AMI: {e}")
        sys.exit(1)

def ensure_security_group_is_open(sg_id):
    """מוודא שפורט 80 פתוח ב-Security Group - קריטי עבור NLB"""
    print(f"🛡️ בודק חוקי אבטחה עבור SG: {sg_id}...")
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }]
        )
        print("✅ פורט 80 נפתח לכניסת תעבורה (0.0.0.0/0).")
    except ec2.exceptions.ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("ℹ️ פורט 80 כבר פתוח ב-SG, ממשיך...")
        else:
            print(f"⚠️ אזהרה בעדכון ה-SG: {e}")

def create_launch_template(ami_id, sg_id):
    """יוצר או מעדכן Launch Template עם ה-AMI וה-SG שנבחרו"""
    print(f"📄 מעדכן Launch Template: {LT_NAME}...")
    try:
        ec2.delete_launch_template(LaunchTemplateName=LT_NAME)
    except:
        pass

    ec2.create_launch_template(
        LaunchTemplateName=LT_NAME,
        LaunchTemplateData={
            'ImageId': ami_id,
            'InstanceType': INSTANCE_TYPE,
            'SecurityGroupIds': [sg_id],
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'ASG-Instance'}]
            }]
        }
    )

def get_or_create_resources():
    """מזהה VPC ו-Subnets עבור ה-Load Balancer"""
    print("🌐 סורק משאבי רשת...")
    vpcs = ec2.describe_vpcs()['Vpcs']
    vpc_data = next((v for v in vpcs if v.get('IsDefault')), vpcs[0])
    vpc_id = vpc_data['VpcId']
    
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
    # NLB דורש לפחות 2 Subnets ב-Availability Zones שונים
    subnet_ids = [s['SubnetId'] for s in subnets[:2]]
    return vpc_id, subnet_ids

def add_scaling_policy():
    """מגדיר Target Tracking Scaling לפי 50% CPU"""
    print(f"📈 מגדיר Scaling Policy ליעד של 50% CPU...")
    try:
        asg.put_scaling_policy(
            AutoScalingGroupName=ASG_NAME,
            PolicyName='CPU-Load-Policy',
            PolicyType='TargetTrackingScaling',
            TargetTrackingConfiguration={
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ASGAverageCPUUtilization'
                },
                'TargetValue': 50.0,
                'DisableScaleIn': False
            }
        )
        print("✅ ה-Scaling Policy הופעל בהצלחה.")
    except Exception as e:
        print(f"⚠️ אזהרה בהגדרת ה-Policy: {e}")

def create_infra():
    """הפונקציה המרכזית להקמת התשתית"""
    # 1. הכנות
    ami_id = get_latest_ami()
    vpc_id, subnet_ids = get_or_create_resources()
    
    # השגת Security Group ופתיחתו לתעבורה
    sgs = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
    sg_id = sgs[0]['GroupId']
    ensure_security_group_is_open(sg_id)
    
    # 2. יצירת ה-Launch Template
    create_launch_template(ami_id, sg_id)

    print(f"🏗️ מקים תשתית NLB (Network Load Balancer)...")
    try:
        # יצירת Target Group עבור NLB (חייב להשתמש ב-TCP)
        tg_arn = elbv2.create_target_group(
            Name=TG_NAME, 
            Protocol='TCP', 
            Port=80, 
            VpcId=vpc_id, 
            TargetType='instance',
            HealthCheckProtocol='TCP',
            HealthCheckPort='80'
        )['TargetGroups'][0]['TargetGroupArn']

        # יצירת NLB
        nlb = elbv2.create_load_balancer(
            Name=NLB_NAME, 
            Subnets=subnet_ids, 
            Type='network', 
            Scheme='internet-facing'
        )['LoadBalancers'][0]
        
        # יצירת ה-Listener בפורט 80
        elbv2.create_listener(
            LoadBalancerArn=nlb['LoadBalancerArn'], 
            Protocol='TCP', 
            Port=80,
            DefaultActions=[{'Type': 'forward', 'TargetGroupArn': tg_arn}]
        )

        # יצירת Auto Scaling Group (2-2-6)
        print(f"🚀 יוצר Auto Scaling Group: {ASG_NAME}...")
        asg.create_auto_scaling_group(
            AutoScalingGroupName=ASG_NAME,
            LaunchTemplate={'LaunchTemplateName': LT_NAME, 'Version': '$Default'},
            MinSize=2,
            MaxSize=6,
            DesiredCapacity=2,
            VPCZoneIdentifier=",".join(subnet_ids),
            TargetGroupARNs=[tg_arn],
            HealthCheckType='ELB',
            HealthCheckGracePeriod=300
        )
        
        # 3. הוספת מדיניות Scaling
        add_scaling_policy()

        print(f"\n✨ התשתית הוקמה בהצלחה!")
        print(f"🔗 כתובת ה-NLB שלך: http://{nlb['DNSName']}")
        print(f"ℹ️  המתן כ-3 דקות עד שהשרתים יהיו Healthy ב-Target Group.")
        
    except Exception as e:
        print(f"❌ שגיאה קריטית בתהליך ההקמה: {e}")

if __name__ == "__main__":
    create_infra()
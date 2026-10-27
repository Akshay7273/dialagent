# DialAgent EC2 deploy (free tier) — console steps

Route decided by boss 2026-10-27: EC2 free tier. Endpoint must stay up
through Nov 9 (OpenCV judging window).

## What the instance runs
Public repo https://github.com/Akshay7273/dialagent, FastAPI + OpenCV 5
headless (no GPU, no system graphics libs needed). Endpoints: GET /
(frontend), GET /health, POST /read (gauge image in, reading + trace out).

## Launch steps (AWS console)
1. Region: ap-south-1 (Mumbai) is fine; any region works.
2. EC2 > Launch instance. Name: dialagent.
3. AMI: Ubuntu Server 24.04 LTS (or 22.04), 64-bit (x86).
4. Instance type: t2.micro (free tier eligible). If t2.micro is unavailable
   in the region, t3.micro is the fallback.
5. Key pair: create new (download the .pem) if shell access may be needed.
6. Network settings: allow SSH (22) from anywhere, and ADD a rule:
   Custom TCP, port 8000, source 0.0.0.0/0 (the demo endpoint).
7. Advanced details > User data: paste the whole
   deploy/ec2-user-data.sh script.
8. Launch. Wait ~5-10 minutes for first boot (pip install of OpenCV
   takes a few minutes on 1 vCPU).

## Verify
- http://<instance-public-IPv4-DNS>:8000/health returns
  {"status":"ok","service":"dialagent"}
- http://<instance-public-IPv4-DNS>:8000/ shows the DialAgent frontend.
- If /health fails, SSH in and read /var/log/dialagent-install.log and
  `systemctl status dialagent`.

## Cost honesty
- t2.micro is free-tier eligible: 750 hours/month for 12 months from
  account creation. One instance running 24/7 through Nov 9 fits inside
  that allowance IF the account is still inside its free-tier window.
- If the free-tier window has expired, t2.micro costs roughly $8-9/month
  on-demand (estimate, ap-south-1). No other AWS service is used, so
  there is nothing else to bill.
- Creating a brand-new AWS account requires a card and phone
  verification (AWS's own requirement, not ours).

## After launch
Give EV the public DNS or IP. EV verifies /health and the frontend from
a fresh browser, records the URL in DEVPOST_DRAFT.md, and the URL goes
into the Devpost submission as the live demo endpoint.

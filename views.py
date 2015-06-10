from django.shortcuts import render_to_response,render
from django.http import HttpResponse,HttpResponseRedirect
from django.template.context import RequestContext
import boto.route53
import boto.ec2.elb
import os,sys
import logging
import re
from tld import get_tld
import json
from awsinfo.aws_server.models import Info



# Create your views here.
logging.basicConfig(level=logging.INFO,
	#format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
	format='%(asctime)s[line:%(lineno)d] %(levelname)s %(message)s',
	datefmt='%a, %Y-%m-%d %H:%M:%S',
	filename='rout53.log',
	filemode='w')
	

def get_domain(request,url):
	logging.info("url: %s" % url)
	rkey = os.environ.get('mread_key')
	rsecret = os.environ.get('mread_secret')

	conn = boto.route53.connection.Route53Connection(aws_access_key_id=rkey,aws_secret_access_key=rsecret)
	domain=get_tld('http://'+url)   #get the domain of full url
	#zone = conn.get_zone(domain)

	try:
		zone = conn.get_zone(domain)
		conn.get_all_rrsets(zone.id)
		records = conn.get_all_rrsets(zone.id)  

	except Exception as e:
		logging.warning(e)
		# if the domain record in another account 
		rkey = os.environ.get('read_key')
		rsecret = os.environ.get('read_secret')
		conn = boto.route53.connection.Route53Connection(aws_access_key_id=rkey,aws_secret_access_key=rsecret)
		if conn.get_zone(domain):
			zone = conn.get_zone(domain)
			records = conn.get_all_rrsets(zone.id)
		else:
			return HttpResponse('{}')  


	result=[]
	results={}

	for record in records:
		if str(record.name) == str(url+'.'):
			if record.type == 'A':
				if record.alias_dns_name == None:   # A record, no alias
					type = "A"
					logging.info("A_url: %s" % url)
					#result.append({'ip':record.resource_records[0]})
					result.append(record.resource_records[0])
					results = {'type':type,'url':url,'result':result}
					results = json.dumps(results)

				else:                               # A record, has alias record
					url=record.alias_dns_name[:-1]  #   remove the last '.' of domain
					logging.info("alias_url: %s" % url)
					return HttpResponseRedirect('/staging/domain/%s' % url) # call get_domain one more time with the alias url
			
			if record.type == 'CNAME':
				url=record.resource_records[0]
				logging.info("Cname_url: %s" % record.resource_records)
				pattern1 = re.compile("elb.amazonaws.com")
				pattern2 = re.compile("edgesuite.net")
				pattern3 = re.compile("cloudfront.net")
				if pattern1.search(record.resource_records[0]):                      # ELB
					type={"CNAME":"ELB"}
					rlist = record.resource_records[0].split('.')  
					#rlist: [u'voga-www-new-489997311', u'ap-southeast-1', u'elb', u'amazonaws', u'com']
					region = rlist[-4]
					if len(rlist) == 5:										
						elb_name = '-'.join(rlist[0].split('-')[:-1])
						logging.info("elb_name: %s" % elb_name)
						elb_conn = boto.ec2.elb.connect_to_region(region,aws_access_key_id=rkey,aws_secret_access_key=rsecret)
						
						try:	
							elb_conn.describe_instance_health(elb_name)
						except Exception as e:
							logging.warning(e)
							# if the elb in another account
							rkey = os.environ.get('read_key')
							rsecret = os.environ.get('read_secret')
						elb_conn = boto.ec2.elb.connect_to_region(region,aws_access_key_id=rkey,aws_secret_access_key=rsecret)

						instances=elb_conn.describe_instance_health(elb_name)
						for i in range(len(instances)):
							result.append(instances[i].instance_id)  # get instance_id
							logging.info("elb_instance_id: %s" % instances[i].instance_id)
						logging.info("cname_elb %s" % results)

					else:
					# write the code later   if len(rlist) != 5
						logging.info("elb name error, has '.' include")
						return HttpResponse("elb name error")
				
				elif pattern2.search(record.resource_records[0]):					 # Akamai CDN
					type = {"CNAME":"AKAMAI"}
					logging.info("cname_akamai %s" % results)

				elif pattern3.search(record.resource_records[0]):					 # Cloudfrond CDN
					type={"CNAME":"CLOUDFRONT"}
					logging.info("cname_cloudfront %s" % results)

				else:					 # Unknown cname
					type={"CNAME":"UNKNOWN"}
					logging.info("cname_unknown %s" % results)
			results = {'type':type,'url':url,'result':result}
			results = json.dumps(results)
	return render_to_response('dns.html', RequestContext(request,{'results':results}))


def get_instance(request,parameter):
	pattern1 = re.compile("i-")
	pattern2 = re.compile("(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})")
	pattern3 = re.compile("172\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})")
	if pattern1.match(parameter):
		result=Info.objects.filter(instance_id=parameter).values()
	if pattern2.match(parameter):
		if pattern3.match(parameter):
			result=Info.objects.filter(lan_ip=parameter).values()[0]
		else:
			result=Info.objects.filter(wan_ip=parameter).values()[0]
		result=json.dumps(result)
	return render_to_response('instance1.html', RequestContext(request,{'result':result}))
		
		
		


from django.conf.urls import patterns, include, url

urlpatterns = patterns('staging.views',
    url(r'^domain/(.*)/$', 'get_domain'),
    url(r'^instance/(.*)/$', 'get_instance'),
)

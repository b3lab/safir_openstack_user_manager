Safir OpenStack User Manager
============================

You may use this library with the register panel patch that we forked from openstack/horizon  

.. sourcecode:: console   

  $ git clone https://github.com/b3lab/safir_openstack_user_manager.git  
  $ cd openstack_user_management/  
  $ sudo pip install .  
  
Make sure you have the clouds.yaml file including the credentials to connect to your OpenStack platform  
inside /etc/openstack directory.  
  
Example clouds.yaml
===================

.. sourcecode:: console 
  
  clouds:  
    cloud-admin:  
      auth:  
        auth_url: http://<controller_hostname>:5000/v3  
        password: <password>  
        project_name: admin  
        username: admin  
        project_domain_name: default  
        user_domain_name: default  
      domain_name: Default  
      identity_api_version: '3'  
      region_name: RegionOne  

  
  
Setup Development Environment
=============================
  
Clone repository  

.. sourcecode:: console 

  $ git clone https://github.com/b3lab/safir_openstack_user_manager.git  
  $ cd openstack_user_management  
  
Create a virtual environment  

.. sourcecode:: console 

  $ virtualenv ./.venv  
  
Switch to virtual environment  

.. sourcecode:: console 

  $ source ./.venv/bin/activate  
  
Install requirements  

.. sourcecode:: console 

  $ pip install -r requirements.txt  
  
Install unittest requirements  

.. sourcecode:: console 

  $ pip install -r test-requirements.txt  


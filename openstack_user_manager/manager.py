# Copyright 2017 TUBITAK B3LAB
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from keystoneauth1 import exceptions as ka_exceptions
from keystoneclient.v3 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from neutronclient.common import exceptions as n_exceptions
from openstack import connection
from openstack import exceptions as o_exceptions
from openstack_user_manager import log
from os_client_config import config as cloud_config

import datetime

try:
    from safirbillingclient import client as safirbilling_client
    from safirbillingclient import exc as sb_exceptions
except:
    pass

LOG = log.get_logger()

INITIAL_CREDIT_AMOUNT=250


class Opts(object):
    def __init__(self, cloud_name, debug=False):
        self.cloud = cloud_name
        self.debug = debug
        self.identity_api_version = '3'


class OpenstackUserManager:
    def __init__(self, config_name):
        opts = Opts(cloud_name=config_name)

        cc = cloud_config.OpenStackConfig()
        LOG.debug("defaults: %s", cc.defaults)

        # clouds.yaml file should either be in the
        # current directory or
        # ~/.config/openstack directory or
        # /etc/openstack directory.
        cloud = cc.get_one_cloud(opts.cloud)
        LOG.debug("cloud cfg: %s", cloud.config)

        # Create a context for a connection to the cloud provider
        self.conn = connection.from_config(cloud_config=cloud,
                                           options=opts)

        identity_api_version = cloud.config['identity_api_version']
        if identity_api_version != '3':
            LOG.error('This version of OpenStack User Management Library '
                      'only supports Identity version 3.')

        # We still need to use neutronclient until openstackclient
        # is able to add interface router, and keystoneclient
        # until openstackclient is able to grant roles to users
        self.neutron_conn = neutron_client.Client(
            session=cloud.get_session_client('network'))
        self.keystone_conn = keystone_client.Client(
            session=cloud.get_session_client('identity'))

        try:
            self.safirbilling_conn = safirbilling_client.Client(
                '1',
                cloud.get_endpoint('billing'),
                session=cloud.get_session_client('billing'))
        except o_exceptions.SDKException as ex:
            LOG.error('Could connect to billing service. ' +
                      ex.message)
            self.safirbilling_conn = None
        except Exception:
            LOG.error('Could connect to billing service.')
            self.safirbilling_conn = None

    def check_username_availability(self,
                                    user_name):
        try:
            user = self.conn.identity.find_user(user_name)
            if user is not None:
                return False
        except ka_exceptions.NotFound:
            return True
        return True

    def check_projectname_availability(self,
                                       project_name):
        try:
            project = self.conn.identity.find_project(project_name)
            if project is not None:
                return False
        except ka_exceptions.NotFound:
            return True
        return True

    def create_project(self, description, project_name,
                       properties, enabled=False):
        try:
            self.conn.identity.create_project(name=project_name,
                                              description=description,
                                              enabled=enabled)
            project = self.conn.identity.find_project(project_name)
            for key, value in properties.items():
                self.conn.identity.update_project(project,
                                                  **{key: value})
        except ka_exceptions.ClientException as ex:
            LOG.error("Project not created. Error: " + ex.message)
            return False

        return True

    def create_user(self, email, user_name, password, enabled=False):
        try:
            self.conn.identity.create_user(name=user_name,
                                           email=email,
                                           password=password,
                                           enabled=enabled)
        except ka_exceptions.ClientException as ex:
            LOG.error("User not created. Error: " + ex.message)
            return False
        return True

    def init_billing_customer(self,
                              project_name,
                              customer_name,
                              company_name,
                              email):
        if self.safirbilling_conn is None:
            return False

        try:
            project = self.conn.identity.find_project(project_name)
        except sb_exceptions.HTTPException as ex:
            LOG.error("Billing customer not created. Error: " + ex.message)
            return False
        except Exception as ex:
            LOG.error("Billing customer not created. Error: " + ex.message)
            return False

        try:
            # Add customer
            self.safirbilling_conn.customer.set(project_id=project.id,
                                                contact_name=customer_name,
                                                company_name=company_name,
                                                mail=email)
        except sb_exceptions.HTTPException as ex:
            pass
        except Exception as ex:
            pass

        try:
            # Load initial credit
            self.safirbilling_conn.credit.load(project_id=project.id,
                                               amount=INITIAL_CREDIT_AMOUNT)
        except sb_exceptions.HTTPException as ex:
            pass
        except Exception as ex:
            pass

        try:
            # Add rating role
            user = self.conn.identity.find_user('cloudkitty')
            if user is not None:
                role = self.conn.identity.find_role('rating')
                if role is not None:
                    self.keystone_conn.roles.grant(role,
                                                   user=user,
                                                   project=project)

            # Add billing role
            user = self.conn.identity.find_user('safirbilling')
            if user is not None:
                role = self.conn.identity.find_role('billing')
                if role is not None:
                    self.keystone_conn.roles.grant(role,
                                                   user=user,
                                                   project=project)
        except sb_exceptions.HTTPException as ex:
            LOG.error("Billing customer not created. Error: " + ex.message)
            return False
        except Exception as ex:
            LOG.error("Billing customer not created. Error: " + ex.message)
            return False
        return True

    def get_billing_customer_status(self, project_id):
        if self.safirbilling_conn is None:
            return None

        try:
            customer = self.safirbilling_conn.customer.get(project_id=project_id)
        except sb_exceptions.HTTPException as ex:
            LOG.error("Billing customer not found. Error: " + ex.message)
            return False
        except Exception as ex:
            LOG.error("Billing customer not found. Error: " + ex.message)
            return False
        return customer.status

    def get_customer_termination_date(self, project_id):
        if self.safirbilling_conn is None:
            return None

        try:
            customer = self.safirbilling_conn.customer.get(project_id=project_id)
            termination_time_limit = self.safirbilling_conn.config.get_termination_time_limit()
            time_delta=int(termination_time_limit[0].value)
            suspend_time = datetime.datetime.strptime(customer.suspend_time,
                                                      "%Y-%m-%dT%H:%M:%S")
            termination_date = (suspend_time +
                                datetime.timedelta(days=time_delta))
        except sb_exceptions.HTTPException as ex:
            LOG.error("Billing customer not found. Error: " + ex.message)
            return None
        except Exception as ex:
            LOG.error("Billing customer not found. Error: " + ex.message)
            return None
        return termination_date

    def get_project(self, project_name):
        try:
            project = self.conn.identity.find_project(project_name)
        except o_exceptions.ResourceNotFound:
            print('ERROR!!! Project ' + project_name + ' not found')
            raise o_exceptions.ResourceNotFound
        return project

    def get_project_from_user(self, role_name, user_name):
        project_id = None
        try:
            role = self.conn.identity.find_role(role_name)
            user = self.get_user(user_name)
            if user:
                ras = self.keystone_conn.role_assignments.list(user=user,
                                                               role=role)
                if len(ras) > 0:
                    project_id = ras[0].scope['project']['id']
        except o_exceptions.ResourceNotFound:
            project_id = None
        except Exception:
            project_id = None
        return project_id

    def get_user(self, user_name):
        try:
            user = self.conn.identity.find_user(user_name,
                                                ignore_missing=False)
        except o_exceptions.ResourceNotFound:
            print('ERROR!!! User ' + user_name + ' not found')
            raise o_exceptions.ResourceNotFound
        return user

    def pair_user_with_project(self, user_name, project_name, role_name):
        try:
            user = self.conn.identity.find_user(user_name)
            project = self.conn.identity.find_project(project_name)
            role = self.conn.identity.find_role(role_name)
            self.keystone_conn.roles.grant(role,
                                           user=user,
                                           project=project)
        except ka_exceptions.ClientException as ex:
            LOG.error("User not paired with project. Error: " +
                      str(ex.message))
            return False
        except Exception as ex:
            LOG.error("User not paired with project. Error: " +
                      str(ex.message))
            return False
        return True

    def update_project_status(self, project_name, enabled):
        try:
            project = self.conn.identity.find_project(project_name)
            self.conn.identity.update_project(project=project,
                                              enabled=enabled)
        except ka_exceptions.ClientException as ex:
            LOG.error("Project status not updated. Error: " + ex.message)
            return False
        return True

    def update_user_status(self, user_name, enabled):
        try:
            user = self.conn.identity.find_user(user_name)
            self.conn.identity.update_user(user=user,
                                           enabled=enabled)
        except ka_exceptions.ClientException as ex:
            LOG.error("User status not updated. Error: " + ex.message)
            return False
        return True

    def update_user_password(self, user_name, password):
        try:
            user = self.conn.identity.find_user(user_name)
            self.conn.identity.update_user(user=user,
                                           password=password)
        except ka_exceptions.ClientException as ex:
            LOG.error("User password not updated. Error: " + ex.message)
            return False
        return True

    def init_network(self, project_name, external_network_name,
                     dns_nameservers, subnet_cidr, subnet_gateway_ip):
        net_name = "private"
        subnet_name = "private"
        router_name = "router"
        try:
            project = self.conn.identity.find_project(project_name)

            # CREATE NETWORK
            net = self.conn.network.create_network(name=net_name,
                                                   project_id=project.id,
                                                   admin_state_up=True)

            # CREATE SUBNET
            subnet = self.conn.network.create_subnet(
                name=subnet_name,
                project_id=project.id,
                network_id=net.id,
                gateway_ip=subnet_gateway_ip,
                enable_dhcp=True,
                ip_version=4,
                cidr=subnet_cidr,
                dns_nameservers=dns_nameservers)

            # CREATE ROUTER
            # router = self.conn.network.create_router(
            #     name=router_name,
            #     tenant_id=project.id,
            #     admin_state_up=True)
            ext_net_id = [e for e in self.neutron_conn.list_networks(
                          )['networks'] if
                          e['name'] == external_network_name][0]['id']
            router_param = {
                'name': router_name,
                'admin_state_up': True,
                'external_gateway_info': {"network_id": ext_net_id},
                'tenant_id': project.id}
            router = self.neutron_conn.create_router(
                {'router': router_param})

            self.neutron_conn.add_interface_router(
                router['router']['id'],
                {'subnet_id': subnet.id,
                 'tenant_id': project.id})

        except n_exceptions.NeutronException as ex:
            LOG.error("Project's initial network could not be defined. "
                      "Error: " + str(ex.message))
            return False
        except ka_exceptions.ClientException as ex:
            LOG.error("Project's initial network could not be defined. "
                      "Error: " + str(ex.message))
            return False
        return True

    def add_ssh_rule(self, project_name):
        try:
            project = self.conn.identity.find_project(project_name)
            default_sec_groups = self.conn.network.security_groups()

            sec_group_id = None
            for sec_group in default_sec_groups:
                if sec_group.project_id == project.id:
                    sec_group_id = sec_group.id

            if sec_group_id is not None:
                self.conn.network.create_security_group_rule(
                    security_group_id=sec_group_id,
                    project_id=project.id,
                    direction='ingress',
                    remote_ip_prefix='0.0.0.0/0',
                    protocol='TCP',
                    port_range_max='22',
                    port_range_min='22',
                    ethertype='IPv4')
        except ka_exceptions.ClientException as ex:
            LOG.error("SSH rule not added. Error: " + ex.message)
            return False
        return True

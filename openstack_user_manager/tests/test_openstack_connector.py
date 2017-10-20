#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from openstack_user_manager.manager import OpenstackUserManager


class TestOpenstackConnector(unittest.TestCase):
    openstack_conn = OpenstackUserManager('cloud-admin')

    def test_template(self):
        self.assertTrue(True)

    def test_openstackclient(self):
        self.assertIsNotNone(self.openstack_conn.conn)
        self.assertIsNotNone(self.openstack_conn.neutron_conn)
        self.assertIsNotNone(self.openstack_conn.keystone_conn)

    def test_username_availability(self):
        self.assertTrue(
            self.openstack_conn.check_username_availability("demo2"))
        self.assertFalse(
            self.openstack_conn.check_username_availability("demo"))

    def test_project_name_availability(self):
        self.assertTrue(
            self.openstack_conn.check_projectname_availability("demo2"))
        self.assertFalse(
            self.openstack_conn.check_projectname_availability("demo"))

    def test_project_creation(self):
        project_properties = {'Client address': 'localhost',
                              'University': 'YTU',
                              'Research Area': 'my research area'}

        self.assertTrue(
            self.openstack_conn.check_projectname_availability(
                "mytestproject"))
        self.openstack_conn.create_project(
            "mydescription",
            "mytestproject",
            project_properties)
        self.assertFalse(
            self.openstack_conn.check_projectname_availability(
                "mytestproject"))
        project = self.openstack_conn.conn.identity.find_project(
            "mytestproject")
        self.openstack_conn.conn.identity.delete_project(project)

    def test_user_creation(self):
        self.assertTrue(
            self.openstack_conn.check_username_availability("testuser"))
        self.openstack_conn.create_user(
            "testuser@testuser.com",
            "testuser",
            "testuser")
        self.assertFalse(
            self.openstack_conn.check_username_availability("testuser"))
        user = self.openstack_conn.conn.identity.find_user('testuser')
        self.openstack_conn.conn.identity.delete_user(user)

    def test_pair_user_with_project(self):
        self.openstack_conn.create_project(
                "mydescription",
                "mytestproject",
                {'prop': 'value'})
        self.openstack_conn.create_user(
                "testuser@testuser.com",
                "testuser",
                "testuser")

        self.assertTrue(self.openstack_conn.pair_user_with_project(
            "testuser",
            "mytestproject",
            "user"))
        project = self.openstack_conn.conn.identity.find_project(
            "mytestproject")
        self.openstack_conn.conn.identity.delete_project(project)
        user = self.openstack_conn.conn.identity.find_user("testuser")
        self.openstack_conn.conn.identity.delete_user(user)

    def test_update_project_status(self):
        self.openstack_conn.create_project(
                "mydescription",
                "mytestproject",
                {'prop': 'value'})
        self.assertTrue(self.openstack_conn.update_project_status(
            "mytestproject",
            enabled=True))
        project = self.openstack_conn.conn.identity.find_project(
            "mytestproject")
        self.openstack_conn.conn.identity.delete_project(project)

    def test_update_user_status(self):
        self.openstack_conn.create_user(
                "testuser@testuser.com",
                "testuser",
                "testuser")
        self.assertTrue(self.openstack_conn.update_user_status("testuser",
                                                               enabled=True))
        user = self.openstack_conn.conn.identity.find_user('testuser')
        self.openstack_conn.conn.identity.delete_user(user)

    @unittest.skip("skipping test_init_network")
    def test_init_network(self):
        subnet_gateway_ip = '10.0.0.1'
        subnet_cidr = '10.0.0.0/24'
        dns_nameservers = ['10.1.0.1']
        self.assertTrue(self.openstack_conn.init_network(
            "a@a.com",
            "ext_net",
            dns_nameservers,
            subnet_cidr,
            subnet_gateway_ip))


if __name__ == "__main__":
    unittest.main(verbosity=2)

data "huaweicloud_vpc" "main" {
  name = var.vpc_name
}

data "huaweicloud_vpc_subnet" "main" {
  name   = var.subnet_name
  vpc_id = data.huaweicloud_vpc.main.id
}

resource "huaweicloud_networking_secgroup" "runtime" {
  name        = "pa-runtime-sg"
  description = "Transitional AgentArts Runtime security group; remove after PUBLIC migration."
}

resource "huaweicloud_networking_secgroup" "rds" {
  name        = "pa-rds-sg"
  description = "Public PostgreSQL access for the Personal Assistant demo RDS."
}

moved {
  from = huaweicloud_networking_secgroup_rule.rds_postgresql_from_runtime
  to   = huaweicloud_networking_secgroup_rule.rds_postgresql_public
}

resource "huaweicloud_networking_secgroup_rule" "rds_postgresql_public" {
  security_group_id = huaweicloud_networking_secgroup.rds.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  ports             = "5432"
  remote_ip_prefix  = "0.0.0.0/0"
  action            = "allow"
  priority          = 1
  description       = "Allow public PostgreSQL access for the demo environment."
}

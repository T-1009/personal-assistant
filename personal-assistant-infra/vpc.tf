data "huaweicloud_vpc" "main" {
  name = var.vpc_name
}

data "huaweicloud_vpc_subnet" "main" {
  name   = var.subnet_name
  vpc_id = data.huaweicloud_vpc.main.id
}

resource "huaweicloud_networking_secgroup" "runtime" {
  name        = "pa-runtime-sg"
  description = "Security group for the Personal Assistant AgentArts Runtime."
}

resource "huaweicloud_networking_secgroup" "rds" {
  name        = "pa-rds-sg"
  description = "Security group for the Personal Assistant RDS instance."
}

resource "huaweicloud_networking_secgroup_rule" "rds_postgresql_from_runtime" {
  security_group_id = huaweicloud_networking_secgroup.rds.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  ports             = "5432"
  remote_group_id   = huaweicloud_networking_secgroup.runtime.id
  action            = "allow"
  priority          = 1
  description       = "Allow PostgreSQL from the AgentArts Runtime only."
}

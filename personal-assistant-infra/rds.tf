resource "huaweicloud_rds_instance" "postgresql" {
  name              = "pa-postgresql"
  charging_mode     = "postPaid"
  flavor            = var.rds_flavor
  vpc_id            = data.huaweicloud_vpc.main.id
  subnet_id         = data.huaweicloud_vpc_subnet.main.id
  security_group_id = huaweicloud_networking_secgroup.rds.id
  availability_zone = [var.rds_availability_zone]

  db {
    type     = "PostgreSQL"
    version  = "17"
    password = var.rds_password
    port     = 5432
  }

  volume {
    type = "CLOUDSSD"
    size = 40
  }

  backup_strategy {
    start_time = "18:00-19:00"
    keep_days  = 7
  }

  tags = {
    app        = "personal-assistant"
    managed_by = "opentofu"
  }
}

resource "huaweicloud_rds_pg_account" "application" {
  instance_id = huaweicloud_rds_instance.postgresql.id
  name        = var.rds_application_username
  password    = var.rds_password
}

resource "huaweicloud_rds_pg_database" "application" {
  instance_id   = huaweicloud_rds_instance.postgresql.id
  name          = var.rds_database_name
  character_set = "UTF8"
  owner         = huaweicloud_rds_pg_account.application.name
}

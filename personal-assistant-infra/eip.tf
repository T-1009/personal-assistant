resource "huaweicloud_vpc_eip" "rds" {
  name        = "pa-rds-eip"
  description = "Public endpoint for the Personal Assistant demo RDS instance."

  publicip {
    type = var.rds_eip_type
  }

  bandwidth {
    name        = "pa-rds-eip-bandwidth"
    size        = var.rds_eip_bandwidth_size
    share_type  = "PER"
    charge_mode = "traffic"
  }

  tags = {
    app        = "personal-assistant"
    managed_by = "opentofu"
  }
}

resource "huaweicloud_rds_instance_eip_associate" "postgresql" {
  instance_id  = huaweicloud_rds_instance.postgresql.id
  public_ip    = huaweicloud_vpc_eip.rds.address
  public_ip_id = huaweicloud_vpc_eip.rds.id
}

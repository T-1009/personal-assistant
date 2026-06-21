output "vpc_id" {
  description = "AgentArts Runtime 使用的 VPC ID"
  value       = data.huaweicloud_vpc.main.id
}

output "subnet_id" {
  description = "AgentArts Runtime 使用的 Subnet ID"
  value       = data.huaweicloud_vpc_subnet.main.id
}

output "runtime_security_group_id" {
  description = "AgentArts Runtime 使用的 Security Group ID"
  value       = huaweicloud_networking_secgroup.runtime.id
}

output "rds_instance_id" {
  description = "RDS PostgreSQL Instance ID"
  value       = huaweicloud_rds_instance.postgresql.id
}

output "rds_private_ips" {
  description = "RDS PostgreSQL Private IP 地址"
  value       = huaweicloud_rds_instance.postgresql.private_ips
}

output "rds_database_name" {
  description = "应用数据库名称"
  value       = huaweicloud_rds_pg_database.application.name
}

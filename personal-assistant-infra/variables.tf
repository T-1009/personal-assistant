# ============================================================
# 变量声明
# ============================================================
# region 等非敏感变量在此声明。
# HuaweiCloud Provider 凭据（AK/SK）通过 Provider 原生环境变量
# HW_ACCESS_KEY / HW_SECRET_KEY 注入，无需通过 Terraform 变量中转。

variable "region" {
  description = "HuaweiCloud 区域"
  type        = string
  default     = "cn-southwest-2"
}

variable "vpc_name" {
  description = "AgentArts Runtime 与 RDS 共用的 VPC 名称"
  type        = string
  default     = "vpc-default-smb"
}

variable "subnet_name" {
  description = "AgentArts Runtime 与 RDS 共用的子网名称"
  type        = string
  default     = "subnet-default-smb"
}

variable "rds_availability_zone" {
  description = "RDS 主可用区"
  type        = string
  default     = "cn-southwest-2f"
}

variable "rds_flavor" {
  description = "RDS PostgreSQL 规格"
  type        = string
  default     = "rds.pg.n1.medium.2"
}

variable "rds_application_username" {
  description = "应用连接 RDS 使用的账号"
  type        = string
  default     = "pa_app"
}

variable "rds_database_name" {
  description = "Personal Assistant 应用数据库名称"
  type        = string
  default     = "personal_assistant"
}

variable "rds_password" {
  description = "RDS 管理账号与初始应用账号密码；只允许通过 TF_VAR_rds_password 注入"
  type        = string
  sensitive   = true
}

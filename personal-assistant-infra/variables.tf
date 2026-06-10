# ============================================================
# 变量声明
# ============================================================
# 敏感变量（ak, sk）通过 terraform.tfvars（gitignored）赋值
# 或通过环境变量 TF_VAR_ak / TF_VAR_sk 注入

variable "region" {
  description = "HuaweiCloud 区域"
  type        = string
  default     = "cn-southwest-2"
}

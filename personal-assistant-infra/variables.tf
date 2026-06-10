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

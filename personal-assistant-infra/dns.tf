# DNS — CNAME 记录
#
# 将 chat.resource-governance.cloud CNAME 到 OBS 静态网站 endpoint，
# 解决 OBS 默认域名强制 Content-Disposition: attachment 的问题。
#
# Zone 由华为云在购买域名时自动创建，通过 CI import 步骤导入 state。
# Zone ID (ff8080829e039233019eac11e92057f8) 来源于首次 apply 失败时
# 华为云 API 错误响应中返回的已有 Zone UUID。

resource "huaweicloud_dns_zone" "main" {
  name        = "resource-governance.cloud"
  description = "Personal Assistant 主域名"
  zone_type   = "public"
}

# CNAME: chat.resource-governance.cloud → OBS website endpoint
resource "huaweicloud_dns_recordset" "chat" {
  zone_id     = huaweicloud_dns_zone.main.id
  name        = "chat.resource-governance.cloud."
  type        = "CNAME"
  ttl         = 300
  records     = ["${huaweicloud_obs_bucket.web_chat.bucket}.obs-website.${var.region}.myhuaweicloud.com."]
  description = "Web Chat 前端入口 → OBS 静态网站"
}

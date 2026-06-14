import { Button } from "@/components/ui/button";
import { Monitor, GitFork, MessageCircle, X } from "lucide-react";

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onMicrosoftLogin: () => void;
}

export function LoginModal({ open, onClose, onMicrosoftLogin }: LoginModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30"
         onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-md mx-4 mb-8 p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-[17px] font-semibold">选择登录方式</h2>
          <button onClick={onClose} className="text-[#7a7a7a] hover:text-[#333333]">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Microsoft — active */}
        <div
          className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 cursor-pointer border-b border-[#e0e0e0]"
          onClick={onMicrosoftLogin}
        >
          <div className="flex items-center gap-3">
            <Monitor className="w-5 h-5 text-primary" />
            <span className="text-[15px]">Microsoft 账号</span>
          </div>
          <span className="text-[13px] text-primary">登录</span>
        </div>

        {/* GitHub — disabled */}
        <div className="flex items-center justify-between p-4 border-b border-[#e0e0e0] opacity-50 cursor-not-allowed">
          <div className="flex items-center gap-3">
            <GitFork className="w-5 h-5" />
            <span className="text-[15px]">GitHub 账号</span>
          </div>
          <span className="text-[12px] text-[#7a7a7a] bg-gray-100 px-2 py-0.5 rounded">即将支持</span>
        </div>

        {/* WeChat — disabled */}
        <div className="flex items-center justify-between p-4 opacity-50 cursor-not-allowed">
          <div className="flex items-center gap-3">
            <MessageCircle className="w-5 h-5" />
            <span className="text-[15px]">微信账号</span>
          </div>
          <span className="text-[12px] text-[#7a7a7a] bg-gray-100 px-2 py-0.5 rounded">即将支持</span>
        </div>

        <Button variant="outline" className="w-full mt-6" onClick={onClose}>
          取消
        </Button>
      </div>
    </div>
  );
}

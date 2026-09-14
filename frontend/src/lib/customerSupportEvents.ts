// 在线咨询浮窗事件集中定义，侧边栏和浮窗通过同一事件解耦通信。by AI.Coding

export const openCustomerSupportEvent = "resolvedesk:open-customer-support"

// 触发客户在线咨询面板，避免侧边栏直接持有浮窗内部状态。by AI.Coding
export function openCustomerSupportPanel() {
  window.dispatchEvent(new CustomEvent(openCustomerSupportEvent))
}

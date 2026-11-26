interface DegradationBannerProps {
  message: string
  onDismiss: () => void
}

export function DegradationBanner({ message, onDismiss }: DegradationBannerProps) {
  return (
    <div className="banner" role="alert">
      <div>
        <strong>降级提示</strong>
        <p>{message}</p>
      </div>
      <button className="banner__close" type="button" onClick={onDismiss} aria-label="关闭提示">
        ×
      </button>
    </div>
  )
}

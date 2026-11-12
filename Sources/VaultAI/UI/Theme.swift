import SwiftUI

enum Theme {
    static let backgroundTop = Color(hex: 0x0B1020)
    static let backgroundBottom = Color(hex: 0x06070D)
    static let accent = Color(hex: 0x5EEAD4)
    static let blue = Color(hex: 0x60A5FA)
    static let violet = Color(hex: 0xA78BFA)
    static let green = Color(hex: 0x34D399)
    static let red = Color(hex: 0xF87171)
    static let amber = Color(hex: 0xFBBF24)
    static let muted = Color(hex: 0x8B93A7)
    static let ink = Color(hex: 0x061018)

    static func stateColor(_ state: DisplayState) -> Color {
        switch state {
        case .ok: return green
        case .sincronizando: return blue
        case .pausa: return amber
        case .erro: return red
        case .idle: return muted
        }
    }

    static func font(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .rounded)
    }
}

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        let red = Double((hex >> 16) & 0xFF) / 255
        let green = Double((hex >> 8) & 0xFF) / 255
        let blue = Double(hex & 0xFF) / 255
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: alpha)
    }
}

// MARK: - Fundo

struct AuroraBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Theme.backgroundTop, Theme.backgroundBottom],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Circle()
                .fill(Theme.blue.opacity(0.30))
                .frame(width: 340, height: 340)
                .blur(radius: 110)
                .offset(x: -170, y: -210)

            Circle()
                .fill(Theme.violet.opacity(0.22))
                .frame(width: 300, height: 300)
                .blur(radius: 120)
                .offset(x: 190, y: 120)

            Circle()
                .fill(Theme.accent.opacity(0.14))
                .frame(width: 260, height: 260)
                .blur(radius: 120)
                .offset(x: 120, y: -260)

            LinearGradient(
                colors: [Color.white.opacity(0.02), Color.clear],
                startPoint: .top,
                endPoint: .bottom
            )
        }
        .ignoresSafeArea()
    }
}

// MARK: - Cartões

struct GlassCard<Content: View>: View {
    var padding: CGFloat
    var glow: Color?
    var content: Content

    init(padding: CGFloat = 18, glow: Color? = nil, @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.glow = glow
        self.content = content()
    }

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(padding)
            .background {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(.ultraThinMaterial)
                    .overlay {
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .fill(
                                LinearGradient(
                                    colors: [Color.white.opacity(0.07), Color.white.opacity(0.015)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                    }
                    .overlay {
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .strokeBorder(
                                LinearGradient(
                                    colors: [Color.white.opacity(0.18), Color.white.opacity(0.04)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ),
                                lineWidth: 1
                            )
                    }
                    .shadow(color: (glow ?? Color.black).opacity(glow == nil ? 0.35 : 0.22), radius: glow == nil ? 18 : 28, y: 10)
            }
    }
}

struct SectionLabel: View {
    let title: String
    var icon: String?

    var body: some View {
        HStack(spacing: 6) {
            if let icon {
                Image(systemName: icon)
                    .font(.system(size: 10, weight: .semibold))
            }
            Text(title.uppercased())
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .tracking(1.1)
        }
        .foregroundStyle(Theme.muted)
    }
}

// MARK: - Estado

struct StatusPill: View {
    let state: DisplayState
    var compact = false

    private var color: Color { Theme.stateColor(state) }

    var body: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(color)
                .frame(width: compact ? 6 : 7, height: compact ? 6 : 7)
                .shadow(color: color.opacity(0.9), radius: 5)
            Text(state.title)
                .font(.system(size: compact ? 10 : 11, weight: .semibold, design: .rounded))
                .foregroundStyle(color)
        }
        .padding(.horizontal, compact ? 9 : 11)
        .padding(.vertical, compact ? 4 : 6)
        .background(Capsule().fill(color.opacity(0.12)))
        .overlay(Capsule().strokeBorder(color.opacity(0.28), lineWidth: 1))
    }
}

// MARK: - Anel de progresso

struct ProgressRing: View {
    let percent: Int?
    let isActive: Bool
    let color: Color
    var size: CGFloat = 96
    var caption: String = "progresso"
    var symbol: String?

    @State private var spinning = false

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.white.opacity(0.07), lineWidth: 9)

            if let percent {
                Circle()
                    .trim(from: 0, to: max(0.02, min(1, Double(percent) / 100)))
                    .stroke(
                        AngularGradient(colors: [color, Theme.blue, color], center: .center),
                        style: StrokeStyle(lineWidth: 9, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
                    .shadow(color: color.opacity(0.5), radius: 8)
                    .animation(.easeInOut(duration: 0.6), value: percent)
            } else if isActive {
                Circle()
                    .trim(from: 0, to: 0.2)
                    .stroke(
                        AngularGradient(colors: [color.opacity(0.1), color, color.opacity(0.1)], center: .center),
                        style: StrokeStyle(lineWidth: 9, lineCap: .round)
                    )
                    .rotationEffect(.degrees(spinning ? 360 : 0))
                    .onAppear {
                        withAnimation(.linear(duration: 1.1).repeatForever(autoreverses: false)) {
                            spinning = true
                        }
                    }
            }

            VStack(spacing: 1) {
                if let percent {
                    Text("\(percent)%")
                        .font(.system(size: size * 0.24, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                } else if isActive {
                    ProgressView()
                        .controlSize(.small)
                        .tint(color)
                } else if let symbol {
                    Image(systemName: symbol)
                        .font(.system(size: size * 0.27, weight: .bold))
                        .foregroundStyle(color)
                } else {
                    Text("—")
                        .font(.system(size: size * 0.22, weight: .bold, design: .rounded))
                        .foregroundStyle(Theme.muted)
                }

                if !caption.isEmpty {
                    Text(caption.uppercased())
                        .font(.system(size: max(7, size * 0.085), weight: .semibold, design: .rounded))
                        .tracking(0.8)
                        .foregroundStyle(Theme.muted)
                }
            }
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Métricas

struct MetricTile: View {
    let icon: String
    let title: String
    let value: Int
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(color)
                Text(title.uppercased())
                    .font(.system(size: 8.5, weight: .bold, design: .rounded))
                    .tracking(0.6)
                    .foregroundStyle(Theme.muted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.65)
            }

            Text("\(value)")
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(value == 0 ? Theme.muted.opacity(0.7) : color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 10)
        .padding(.vertical, 9)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color.white.opacity(0.035))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(color.opacity(value == 0 ? 0.06 : 0.20), lineWidth: 1)
        )
    }
}

struct CompactMetric: View {
    let icon: String
    let title: String
    let value: Int
    let color: Color

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(color)
                .frame(width: 20, height: 20)
                .background(Circle().fill(color.opacity(0.12)))

            VStack(alignment: .leading, spacing: 0) {
                Text("\(value)")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .monospacedDigit()
                Text(title)
                    .font(.system(size: 9, weight: .medium, design: .rounded))
                    .foregroundStyle(Theme.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Botões

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .foregroundStyle(Theme.ink)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 13)
            .background(
                Capsule().fill(
                    LinearGradient(colors: [Theme.accent, Theme.blue], startPoint: .leading, endPoint: .trailing)
                )
            )
            .shadow(color: Theme.accent.opacity(0.35), radius: 14, y: 6)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .semibold, design: .rounded))
            .foregroundStyle(.white.opacity(0.92))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                Capsule()
                    .fill(Color.white.opacity(configuration.isPressed ? 0.12 : 0.06))
            )
            .overlay(Capsule().strokeBorder(Color.white.opacity(0.12), lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct IconActionButton: View {
    let icon: String
    let title: String
    let color: Color
    let action: () -> Void

    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            VStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(color)
                Text(title)
                    .font(.system(size: 9, weight: .medium, design: .rounded))
                    .foregroundStyle(Theme.muted)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.white.opacity(hovering ? 0.08 : 0.035))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(Color.white.opacity(hovering ? 0.16 : 0.07), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
    }
}

struct HeaderIconButton: View {
    let icon: String
    var help: String = ""
    let action: () -> Void

    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(hovering ? Color.white : Theme.muted)
                .frame(width: 22, height: 22)
                .background(
                    Circle().fill(Color.white.opacity(hovering ? 0.12 : 0.05))
                )
                .overlay(Circle().strokeBorder(Color.white.opacity(0.08), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .help(help)
    }
}

// MARK: - Logo

struct LogoMark: View {
    var size: CGFloat = 48

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.29, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Theme.accent, Theme.blue, Theme.violet],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.29, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.35), lineWidth: 1)
                )
                .shadow(color: Theme.blue.opacity(0.45), radius: size * 0.28, y: size * 0.10)

            Image(systemName: "externaldrive.fill.badge.icloud")
                .font(.system(size: size * 0.42, weight: .semibold))
                .foregroundStyle(Theme.ink.opacity(0.85))
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Barra de progresso

struct GradientProgressBar: View {
    let percent: Int?
    let isActive: Bool
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.white.opacity(0.07))

                if let percent {
                    Capsule()
                        .fill(LinearGradient(colors: [color, Theme.blue], startPoint: .leading, endPoint: .trailing))
                        .frame(width: max(6, geo.size.width * CGFloat(percent) / 100))
                        .shadow(color: color.opacity(0.5), radius: 5)
                        .animation(.easeInOut(duration: 0.6), value: percent)
                } else if isActive {
                    TimelineView(.animation(minimumInterval: 1 / 30)) { context in
                        let cycle = context.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.6) / 1.6
                        Capsule()
                            .fill(LinearGradient(colors: [color.opacity(0.2), color, color.opacity(0.2)], startPoint: .leading, endPoint: .trailing))
                            .frame(width: max(40, geo.size.width * 0.28))
                            .offset(x: (geo.size.width + 40) * cycle - 40)
                    }
                    .clipShape(Capsule())
                }
            }
        }
        .frame(height: 6)
    }
}

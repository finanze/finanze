import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { useTheme } from "../../context/ThemeContext"
import { useI18n } from "../../i18n"
import { getThemeColors, spacing } from "../../theme"
import { OngoingProject } from "../../../domain"
import { getDaysStatus } from "../../utils/financialDataUtils"
import { ASSET_TYPE_COLOR_MAP } from "../../utils/colorUtils"
import { getIconForAssetType } from "../../utils/iconUtils"
import { SensitiveText } from "../ui"

interface OngoingInvestmentsProps {
  projects: OngoingProject[]
}

export function OngoingInvestments({ projects }: OngoingInvestmentsProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)
  const { t } = useI18n()

  /**
   * Get the maturity date to display.
   * If the standard maturity date is past and there's an extended maturity, use the extended.
   */
  const getDisplayMaturity = (project: OngoingProject): string => {
    const now = new Date()
    const maturityDate = new Date(project.maturity)

    // If maturity is past and we have extended maturity, use extended
    if (maturityDate < now && project.extendedMaturity) {
      return project.extendedMaturity
    }
    return project.maturity
  }

  if (projects.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
          {t.dashboard.ongoingInvestments}
        </Text>
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            {t.dashboard.noInvestments}
          </Text>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
        {t.dashboard.ongoingInvestments}
      </Text>

      <View style={styles.list}>
        {projects.slice(0, 5).map((project, index) => {
          const daysStatus = getDaysStatus(
            project.maturity,
            project.extendedMaturity,
          )
          const displayMaturity = getDisplayMaturity(project)

          return (
            <View
              key={`${project.name}-${index}`}
              style={[
                styles.item,
                index < Math.min(projects.length, 5) - 1 && {
                  borderBottomWidth: StyleSheet.hairlineWidth,
                  borderBottomColor: colors.border,
                },
              ]}
            >
              <View style={styles.header}>
                <View style={styles.typeIcon}>
                  {getIconForAssetType(project.type, {
                    color:
                      ASSET_TYPE_COLOR_MAP[project.type] || colors.textMuted,
                    size: 14,
                  })}
                </View>
                <Text
                  style={[styles.name, { color: colors.text }]}
                  numberOfLines={1}
                >
                  {project.name}
                </Text>
              </View>

              <View style={styles.details}>
                <View style={styles.detailRow}>
                  <Text
                    style={[styles.detailLabel, { color: colors.textMuted }]}
                  >
                    {t.investments.amount}
                  </Text>
                  <SensitiveText
                    kind="currency"
                    value={project.value}
                    currency={project.currency}
                    style={[styles.detailValue, { color: colors.text }]}
                  />
                </View>

                <View style={styles.detailRow}>
                  <Text
                    style={[styles.detailLabel, { color: colors.textMuted }]}
                  >
                    {t.investments.return}
                  </Text>
                  <SensitiveText
                    kind="percentage"
                    value={project.roi}
                    decimals={2}
                    style={[styles.detailValue, { color: colors.success[500] }]}
                  />
                </View>

                <View style={styles.detailRow}>
                  <Text
                    style={[styles.detailLabel, { color: colors.textMuted }]}
                  >
                    {t.investments.maturity}
                  </Text>
                  <View style={styles.maturityContainer}>
                    <SensitiveText
                      kind="date"
                      value={displayMaturity}
                      style={[styles.detailValue, { color: colors.text }]}
                    />
                    {/* Days badge after maturity */}
                    <View
                      style={[
                        styles.daysBadge,
                        {
                          backgroundColor: daysStatus.isDelayed
                            ? colors.danger[500] + "20"
                            : daysStatus.days <= 7
                              ? colors.warning[500] + "20"
                              : colors.success[500] + "15",
                        },
                      ]}
                    >
                      <Text
                        style={[
                          styles.daysBadgeText,
                          {
                            color: daysStatus.isDelayed
                              ? colors.danger[500]
                              : daysStatus.days <= 7
                                ? colors.warning[500]
                                : colors.success[500],
                          },
                        ]}
                      >
                        {daysStatus.days}
                        {daysStatus.isDelayed
                          ? t.dashboard.daysDelay
                          : t.dashboard.daysLeft}
                      </Text>
                    </View>
                  </View>
                </View>
              </View>
            </View>
          )
        })}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  section: {
    paddingTop: spacing.md,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.5,
    marginBottom: spacing.md,
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: "300",
  },
  list: {
    gap: 0,
  },
  item: {
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  name: {
    fontSize: 14,
    fontWeight: "400",
    flex: 1,
    letterSpacing: 0.2,
  },
  typeIcon: {
    width: 18,
    alignItems: "flex-start",
  },
  daysBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: spacing.xs,
  },
  daysBadgeText: {
    fontSize: 10,
    fontWeight: "500",
    letterSpacing: 0.3,
  },
  details: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
    marginTop: 4,
  },
  detailRow: {
    gap: 2,
  },
  detailLabel: {
    fontSize: 10,
    fontWeight: "300",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  detailValue: {
    fontSize: 13,
    fontWeight: "500",
  },
  maturityContainer: {
    flexDirection: "row",
    alignItems: "center",
  },
})

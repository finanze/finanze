import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { getAllRealEstate } from "@/services/api"
import type { RealEstate } from "@/types"
import { RealEstateFormModal } from "@/components/RealEstateFormModal"

export default function RealEstateEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const [property, setProperty] = useState<RealEstate | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const list = await getAllRealEstate()
        const found = list.find(p => p.id === id) || null
        setProperty(found)
      } catch (e) {
        console.error(e)
        showToast(t.realEstate.errors.loadFailed, "error")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  if (loading) return null
  if (!property) return null

  return (
    <div className="pb-6">
      <RealEstateFormModal
        isOpen={true}
        onClose={() => navigate(`/real-estate/${property.id}`)}
        property={property}
        onSuccess={() => navigate(`/real-estate/${property.id}`)}
      />
    </div>
  )
}

import { createClient } from '@/utils/supabase/server'
import { cookies } from 'next/headers'

export default async function Page() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  // Consultando a tabela real que criamos no Estágio 4
  const { data: perfis } = await supabase.from('perfis_dna').select()

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Painel de Controle: Projeto infans</h1>
      <ul>
        {perfis?.map((perfil) => (
          <li key={perfil.id}>
            <strong>Perfil {perfil.perfil_id}:</strong> {perfil.tom_de_voz} - <em>Status: {perfil.status}</em>
          </li>
        ))}
      </ul>
    </div>
  )
}

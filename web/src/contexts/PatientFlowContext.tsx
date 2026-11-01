/**
 * web/src/contexts/PatientFlowContext.tsx
 * ----------------------------------------
 * Global patient flow context untuk melacak pasien yang sama
 * melalui seluruh alur: BPMH → Analisis → Telaah → Selesai
 *
 * Ini memastikan bahwa ketika pasien diambil dari antrean (misal #0231),
 * pasien yang sama mengalir ke semua tahap berikutnya.
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getWorklistV1, claimEncounterV1, type WorklistItemV1 } from '../lib/apiClient'

export type WorkflowStage = 
  | 'QUEUE_BPMH'      // Antrean BPMH
  | 'BPMH'            // Sedang mengisi BPMH
  | 'QUEUE_REVIEW'    // Antrean Telaah (setelah BPMH selesai)
  | 'ANALYSIS'        // Sedang analisis
  | 'REVIEW'          // Sedang telaah farmasi
  | 'COMPLETED'       // Selesai (APPROVE/EDIT/DITOLAK)

interface PatientFlowState {
  currentPatient: WorklistItemV1 | null
  currentStage: WorkflowStage
  patientHistory: Array<{
    encounter_id: string
    stage: WorkflowStage
    timestamp: string
    action?: string
  }>
}

interface PatientFlowContextValue {
  // Current patient state
  currentPatient: WorklistItemV1 | null
  currentStage: WorkflowStage
  patientHistory: PatientFlowState['patientHistory']
  
  // Actions
  selectPatient: (patient: WorklistItemV1) => void
  claimAndSelectPatient: (patient: WorklistItemV1) => Promise<void>
  advanceStage: (nextStage: WorkflowStage, action?: string) => void
  clearPatient: () => void
  
  // Queue operations
  getNextFromQueue: (queueType: 'BPMH' | 'REVIEW') => Promise<WorklistItemV1 | null>
  
  // Helpers
  isPatientInStage: (stage: WorkflowStage) => boolean
  canProceedToStage: (nextStage: WorkflowStage) => boolean
}

const PatientFlowContext = createContext<PatientFlowContextValue | null>(null)

export function PatientFlowProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<PatientFlowState>({
    currentPatient: null,
    currentStage: 'QUEUE_BPMH',
    patientHistory: [],
  })

  // Log stage transition
  const logTransition = useCallback((encounterId: string, stage: WorkflowStage, action?: string) => {
    setState(prev => ({
      ...prev,
      currentStage: stage,
      patientHistory: [
        ...prev.patientHistory,
        {
          encounter_id: encounterId,
          stage,
          timestamp: new Date().toISOString(),
          action,
        }
      ]
    }))
  }, [])

  // Select a patient (from queue or worklist)
  const selectPatient = useCallback((patient: WorklistItemV1) => {
    setState(prev => ({
      ...prev,
      currentPatient: patient,
      currentStage: determineStageFromStatus(patient.workflow_status),
      patientHistory: prev.currentPatient?.encounter_id !== patient.encounter_id 
        ? [{
            encounter_id: patient.encounter_id,
            stage: determineStageFromStatus(patient.workflow_status),
            timestamp: new Date().toISOString(),
          }]
        : prev.patientHistory
    }))
  }, [])

  // Claim and select a patient atomically
  const claimAndSelectPatient = useCallback(async (patient: WorklistItemV1) => {
    try {
      await claimEncounterV1(patient.encounter_id, patient.row_version)
      selectPatient(patient)
      
      // Invalidate worklist to reflect claim
      queryClient.invalidateQueries({ queryKey: ['worklist'] })
    } catch (error) {
      console.error('Failed to claim patient:', error)
      throw error
    }
  }, [selectPatient, queryClient])

  // Advance to next stage
  const advanceStage = useCallback((nextStage: WorkflowStage, action?: string) => {
    if (!state.currentPatient) return
    
    logTransition(state.currentPatient.encounter_id, nextStage, action)
  }, [state.currentPatient, logTransition])

  // Clear current patient
  const clearPatient = useCallback(() => {
    setState({
      currentPatient: null,
      currentStage: 'QUEUE_BPMH',
      patientHistory: [],
    })
  }, [])

  // Get next patient from queue (BPMH or REVIEW)
  const getNextFromQueue = useCallback(async (queueType: 'BPMH' | 'REVIEW'): Promise<WorklistItemV1 | null> => {
    try {
      const data = await getWorklistV1({
        page_size: 1,
        // Filter by workflow status based on queue type
      })
      
      // Find first unclaimed patient that matches the queue type
      const nextPatient = data.items.find(item => {
        const isUnclaimed = !item.claimed_by
        const matchesQueue = queueType === 'BPMH' 
          ? item.workflow_status === 'MENUNGGU_BPMH'
          : ['MENUNGGU_TELAAH', 'DRAFT_REVIEW'].includes(item.workflow_status)
        return isUnclaimed && matchesQueue
      })
      
      if (nextPatient) {
        await claimAndSelectPatient(nextPatient)
        return nextPatient
      }
      
      return null
    } catch (error) {
      console.error('Failed to get next from queue:', error)
      return null
    }
  }, [claimAndSelectPatient])

  // Check if patient is in specific stage
  const isPatientInStage = useCallback((stage: WorkflowStage): boolean => {
    return state.currentStage === stage
  }, [state.currentStage])

  // Check if can proceed to next stage
  const canProceedToStage = useCallback((nextStage: WorkflowStage): boolean => {
    const validTransitions: Record<WorkflowStage, WorkflowStage[]> = {
      'QUEUE_BPMH': ['BPMH'],
      'BPMH': ['QUEUE_REVIEW', 'ANALYSIS'],
      'QUEUE_REVIEW': ['REVIEW'],
      'ANALYSIS': ['REVIEW', 'QUEUE_REVIEW'],
      'REVIEW': ['COMPLETED'],
      'COMPLETED': [],
    }
    
    return validTransitions[state.currentStage]?.includes(nextStage) ?? false
  }, [state.currentStage])

  return (
    <PatientFlowContext.Provider
      value={{
        currentPatient: state.currentPatient,
        currentStage: state.currentStage,
        patientHistory: state.patientHistory,
        selectPatient,
        claimAndSelectPatient,
        advanceStage,
        clearPatient,
        getNextFromQueue,
        isPatientInStage,
        canProceedToStage,
      }}
    >
      {children}
    </PatientFlowContext.Provider>
  )
}

export function usePatientFlow() {
  const context = useContext(PatientFlowContext)
  if (!context) {
    throw new Error('usePatientFlow must be used within PatientFlowProvider')
  }
  return context
}

// Helper: Determine stage from workflow status
function determineStageFromStatus(status: string): WorkflowStage {
  switch (status) {
    case 'MENUNGGU_BPMH':
      return 'QUEUE_BPMH'
    case 'BPMH_LENGKAP':
    case 'DALAM_ANALISIS':
      return 'ANALYSIS'
    case 'MENUNGGU_TELAAH':
    case 'DRAFT_REVIEW':
      return 'QUEUE_REVIEW'
    case 'SELESAI_APPROVE':
    case 'SELESAI_EDIT':
    case 'DITOLAK':
    case 'ESKALASI':
      return 'COMPLETED'
    default:
      return 'QUEUE_BPMH'
  }
}

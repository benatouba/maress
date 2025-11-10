import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import StudySiteEditDialog from '@/components/maps/StudySiteEditDialog.vue'
import { useStudySitesStore } from '@/stores/studySites'
import { mockStudySite } from '../mocks/api-mocks'
import { setupTest, teardownTest } from '../utils/test-utils'

describe('StudySiteEditDialog', () => {
  let wrapper: any
  let store: ReturnType<typeof useStudySitesStore>

  const createWrapper = (props = {}) => {
    return mount(StudySiteEditDialog, {
      props: {
        modelValue: false,
        studySite: null,
        ...props
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          VDialog: { template: '<div v-if="modelValue"><slot /></div>', props: ['modelValue'] },
          VCard: { template: '<div><slot /></div>' },
          VCardTitle: { template: '<div><slot /></div>' },
          VCardSubtitle: { template: '<div><slot /></div>' },
          VCardText: { template: '<div><slot /></div>' },
          VCardActions: { template: '<div><slot /></div>' },
          VForm: { template: '<form><slot /></form>' },
          VTextField: {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue', 'label', 'rules']
          },
          VTextarea: {
            template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue']
          },
          VRow: { template: '<div><slot /></div>' },
          VCol: { template: '<div><slot /></div>' },
          VBtn: {
            template: '<button @click="$emit(\'click\')" :disabled="disabled"><slot /></button>',
            props: ['disabled', 'loading']
          },
          VChip: { template: '<span><slot /></span>' },
          VExpansionPanels: { template: '<div><slot /></div>' },
          VExpansionPanel: { template: '<div><slot /></div>' },
          VExpansionPanelTitle: { template: '<div><slot /></div>' },
          VExpansionPanelText: { template: '<div><slot /></div>' },
          VIcon: { template: '<i />' }
        }
      }
    })
  }

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())
    store = useStudySitesStore()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    teardownTest()
  })

  describe('Rendering', () => {
    it('should render when modelValue is true', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })

      expect(wrapper.find('[data-test="edit-dialog"]').exists()).toBe(false) // Stubbed, won't have data-test
      expect(wrapper.text()).toContain('Edit Study Site')
    })

    it('should not render when modelValue is false', () => {
      wrapper = createWrapper({
        modelValue: false,
        studySite: mockStudySite
      })

      // With stubbed VDialog, it won't render content when modelValue is false
      expect(wrapper.text()).not.toContain('Edit Study Site')
    })

    it('should display study site data', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })

      const inputs = wrapper.findAll('input')
      const textareas = wrapper.findAll('textarea')

      // Check that form elements are rendered
      expect(inputs.length).toBeGreaterThan(0)
      expect(textareas.length).toBeGreaterThan(0)
    })

    it('should show manual badge for manual sites', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: { ...mockStudySite, is_manual: true }
      })

      expect(wrapper.text()).toContain('Manual')
    })

    it('should show automatic badge for automatic sites', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: { ...mockStudySite, is_manual: false }
      })

      expect(wrapper.text()).toContain('Automatic')
    })
  })

  describe('Form Interaction', () => {
    beforeEach(() => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })
    })

    it('should initialize form with study site data', async () => {
      await wrapper.vm.$nextTick()

      // Check that form is initialized (internal state)
      expect(wrapper.vm.form.name).toBe(mockStudySite.name)
      expect(wrapper.vm.form.latitude).toBe(mockStudySite.latitude)
      expect(wrapper.vm.form.longitude).toBe(mockStudySite.longitude)
    })

    it('should update form data on input', async () => {
      const nameInput = wrapper.findAll('input')[0]
      await nameInput.setValue('New Site Name')

      expect(wrapper.vm.form.name).toBe('New Site Name')
    })
  })

  describe('Save Functionality', () => {
    beforeEach(() => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })
    })

    it('should call updateStudySite on save', async () => {
      vi.spyOn(store, 'updateStudySite').mockResolvedValue(mockStudySite)

      const saveButton = wrapper.findAll('button').find((btn: any) =>
        btn.text().includes('Save')
      )
      await saveButton.trigger('click')

      await wrapper.vm.$nextTick()

      expect(store.updateStudySite).toHaveBeenCalled()
    })

    it('should emit saved event on successful save', async () => {
      vi.spyOn(store, 'updateStudySite').mockResolvedValue(mockStudySite)

      await wrapper.vm.handleSave()
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('saved')).toBeTruthy()
    })

    it('should emit update:modelValue on successful save', async () => {
      vi.spyOn(store, 'updateStudySite').mockResolvedValue(mockStudySite)

      await wrapper.vm.handleSave()
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
    })

    it('should not save if form is invalid', async () => {
      // Set invalid latitude
      wrapper.vm.form.latitude = 999
      wrapper.vm.formValid = false

      vi.spyOn(store, 'updateStudySite')

      await wrapper.vm.handleSave()

      expect(store.updateStudySite).not.toHaveBeenCalled()
    })
  })

  describe('Delete Functionality', () => {
    beforeEach(() => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })
      global.confirm = vi.fn(() => true)
    })

    it('should show confirmation dialog on delete', async () => {
      await wrapper.vm.handleDelete()

      expect(global.confirm).toHaveBeenCalledWith(
        expect.stringContaining(mockStudySite.name!)
      )
    })

    it('should call deleteStudySite on confirmed delete', async () => {
      vi.spyOn(store, 'deleteStudySite').mockResolvedValue(true)

      await wrapper.vm.handleDelete()
      await wrapper.vm.$nextTick()

      expect(store.deleteStudySite).toHaveBeenCalledWith(mockStudySite.id)
    })

    it('should emit deleted event on successful delete', async () => {
      vi.spyOn(store, 'deleteStudySite').mockResolvedValue(true)

      await wrapper.vm.handleDelete()
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('deleted')).toBeTruthy()
    })

    it('should not delete if user cancels', async () => {
      global.confirm = vi.fn(() => false)
      vi.spyOn(store, 'deleteStudySite')

      await wrapper.vm.handleDelete()

      expect(store.deleteStudySite).not.toHaveBeenCalled()
    })
  })

  describe('Cancel Functionality', () => {
    it('should emit update:modelValue on cancel', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })

      wrapper.vm.handleCancel()

      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
    })
  })

  describe('Validation', () => {
    beforeEach(() => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })
    })

    it('should validate required fields', () => {
      expect(wrapper.vm.rules.required('')).toContain('Required')
      expect(wrapper.vm.rules.required('value')).toBe(true)
    })

    it('should validate latitude range', () => {
      expect(wrapper.vm.rules.latitude(-91)).toContain('between -90 and 90')
      expect(wrapper.vm.rules.latitude(91)).toContain('between -90 and 90')
      expect(wrapper.vm.rules.latitude(45)).toBe(true)
    })

    it('should validate longitude range', () => {
      expect(wrapper.vm.rules.longitude(-181)).toContain('between -180 and 180')
      expect(wrapper.vm.rules.longitude(181)).toContain('between -180 and 180')
      expect(wrapper.vm.rules.longitude(-122)).toBe(true)
    })

    it('should validate score range', () => {
      expect(wrapper.vm.rules.score(-0.1)).toContain('between 0 and 1')
      expect(wrapper.vm.rules.score(1.1)).toContain('between 0 and 1')
      expect(wrapper.vm.rules.score(0.85)).toBe(true)
    })
  })

  describe('Date Formatting', () => {
    it('should format dates correctly', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })

      const formatted = wrapper.vm.formatDate('2024-01-15T10:30:00Z')
      expect(formatted).toBeTruthy()
      expect(typeof formatted).toBe('string')
    })

    it('should return N/A for invalid dates', () => {
      wrapper = createWrapper({
        modelValue: true,
        studySite: mockStudySite
      })

      expect(wrapper.vm.formatDate(null)).toBe('N/A')
      expect(wrapper.vm.formatDate('')).toBe('N/A')
    })
  })
})
